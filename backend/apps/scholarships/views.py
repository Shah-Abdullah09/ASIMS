from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import has_role
from apps.documents.validation import inspect_upload

from .checklist import build_checklist, max_files
from .choices import ApplicationStatus
from .declarations import sync_declarations
from .models import Application, ApplicationDocument, Declaration, ScholarshipCycle, StatusChange
from .serializers import (SECTIONS, ApplicationCreateSerializer, ApplicationDetailSerializer,
                          ApplicationListSerializer, CycleSerializer, DeclarationSerializer,
                          DocumentReplaceSerializer, DocumentSerializer, DocumentUploadSerializer,
                          ReceiveSerializer, ReviewListSerializer, StaffApplicationDetailSerializer,
                          StatusUpdateSerializer, scan_upload_allowed)
from .submission import readiness

DETAIL_PREFETCH = ['household_members', 'studying_members', 'parents', 'earning_members', 'asset_income',
                   'utility_months', 'vehicles', 'land_holdings', 'asset_worth', 'education_records',
                   'previous_scholarships', 'status_history__changed_by']

# Staff who may open any applicant's files (the review chain adds more roles in Phase 3)
DOCUMENT_REVIEWER_ROLES = (Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR)

LOCKED_MESSAGE = 'This application has been submitted and can no longer be changed.'


class OpenCycleListView(ListAPIView):
    """Scholarship cycles a student can apply to today."""

    permission_classes = [has_role(Role.STUDENT)]
    serializer_class = CycleSerializer
    pagination_class = None

    def get_queryset(self):
        today = timezone.localdate()
        return ScholarshipCycle.objects.filter(is_active=True, opens_on__lte=today, closes_on__gte=today)


def stored_name(ext):
    """A name for storage; the upload path replaces it with a random one but keeps this extension."""
    return f'upload.{ext}'


class StudentApplicationViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                                viewsets.GenericViewSet):
    """A student's own applications. Other students' applications are invisible (404)."""

    permission_classes = [has_role(Role.STUDENT)]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = Application.objects.filter(student=self.request.user).select_related('cycle', 'student__department')
        if self.action != 'list':
            qs = qs.prefetch_related(*DETAIL_PREFETCH)
        return qs

    def get_serializer_class(self):
        return {'list': ApplicationListSerializer, 'create': ApplicationCreateSerializer}.get(
            self.action, ApplicationDetailSerializer)

    def create(self, request, *args, **kwargs):
        serializer = ApplicationCreateSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        app = serializer.save()
        return Response(ApplicationDetailSerializer(self._fresh(app)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path=r'sections/(?P<section>[a-z_]+)')
    def save_section(self, request, pk=None, section=None):
        """Save one wizard step as a draft."""
        serializer_class = SECTIONS.get(section)
        if serializer_class is None:
            raise NotFound(f'Unknown section "{section}". Valid sections: {", ".join(SECTIONS)}.')
        app = self._editable_app()
        serializer = serializer_class(app, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ApplicationDetailSerializer(self._fresh(app)).data)

    # ---------- documents ----------

    @action(detail=True, methods=['get', 'post'], url_path='documents')
    def documents(self, request, pk=None):
        """GET: the checklist with every slot, its rule and its files. POST: upload one file into a slot."""
        if request.method == 'GET':
            return Response(build_checklist(self.get_object(), DocumentSerializer))

        app = self._editable_app()
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slot, upload = serializer.validated_data['slot'], serializer.validated_data['file']
        limit = max_files(slot)
        if app.documents.filter(slot=slot).count() >= limit:
            raise ValidationError({'file': f'This slot already has the maximum of {limit} files. '
                                           'Delete or replace one first.'})
        content_type, ext = self._inspect(upload)
        original_name = upload.name
        upload.name = stored_name(ext)
        doc = ApplicationDocument.objects.create(
            application=app, slot=slot, file=upload, original_name=original_name[:255],
            content_type=content_type, size=upload.size, uploaded_by=request.user)
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put', 'delete'], url_path=r'documents/(?P<doc_id>\d+)')
    def document_detail(self, request, pk=None, doc_id=None):
        """PUT: replace the file in place (same slot). DELETE: remove it. Drafts only."""
        app = self._editable_app()
        doc = get_object_or_404(app.documents, pk=doc_id)
        if request.method == 'DELETE':
            with transaction.atomic():
                doc.delete()
                transaction.on_commit(lambda name=doc.file.name, storage=doc.file.storage: storage.delete(name))
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = DocumentReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data['file']
        content_type, ext = self._inspect(upload)
        old_name, storage = doc.file.name, doc.file.storage
        doc.original_name = upload.name[:255]
        upload.name = stored_name(ext)
        doc.file = upload
        doc.content_type, doc.size = content_type, upload.size
        doc.uploaded_by, doc.uploaded_at = request.user, timezone.now()
        with transaction.atomic():
            doc.save()
            transaction.on_commit(lambda: storage.delete(old_name))
        return Response(DocumentSerializer(doc).data)

    # ---------- submit ----------

    @action(detail=True, methods=['get'])
    def readiness(self, request, pk=None):
        """What still stops this application from being submitted, grouped by wizard step."""
        return Response(readiness(self.get_object()))

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        app = self._editable_app()
        result = readiness(app)
        if not result['ready']:
            return Response({'detail': 'The application is not complete yet.', **result},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            sync_declarations(app)
            app.status = ApplicationStatus.PENDING
            app.submitted_at = timezone.now()
            app.save(update_fields=['status', 'submitted_at', 'updated_at'])
            StatusChange.objects.create(application=app, from_status=ApplicationStatus.DRAFT,
                                        to_status=ApplicationStatus.PENDING, remarks='Submitted by the student.',
                                        changed_by=request.user)
        self._send_confirmation(app)
        return Response(ApplicationDetailSerializer(self._fresh(app)).data)

    @staticmethod
    def _send_confirmation(app):
        count = app.declarations.count()
        form2 = (f'You still need to upload the scan of {count} stamp-paper income declaration(s) and hand the '
                 'original(s) to the Placement Office.' if count else '')
        send_mail(
            f'ASIMS: scholarship application #{app.pk} submitted',
            f'Dear {app.applicant_name},\n\nYour {app.cycle.name} need based financial grant application '
            f'(number {app.pk}) was submitted on {timezone.localtime(app.submitted_at):%d %b %Y %H:%M}.\n'
            f'{form2}\n\nYou can follow its status in ASIMS.',
            None, [app.email or app.student.email])

    # ---------- Form 2 declarations ----------

    @action(detail=True, methods=['get'])
    def declarations(self, request, pk=None):
        """Printable declaration text for each earning parent or guardian, with scan and receipt status."""
        app = self.get_object()
        return Response(DeclarationSerializer(self._declarations(app), many=True).data)

    @action(detail=True, methods=['post'], url_path=r'declarations/(?P<declaration_id>\d+)/scan')
    def declaration_scan(self, request, pk=None, declaration_id=None):
        """Upload or replace the scan of the signed stamp paper. Allowed after submission too,
        until the office has received the original."""
        app = self.get_object()
        declaration = get_object_or_404(self._declarations(app), pk=declaration_id)
        if not scan_upload_allowed(declaration):
            raise PermissionDenied('The office has already received this declaration, so the scan cannot be changed.')
        serializer = DocumentReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data['file']
        content_type, ext = self._inspect(upload)
        old = (declaration.scan.storage, declaration.scan.name) if declaration.scan else None
        declaration.scan_original_name = upload.name[:255]
        upload.name = stored_name(ext)
        declaration.scan = upload
        declaration.scan_content_type, declaration.scan_size = content_type, upload.size
        declaration.scan_uploaded_by, declaration.scan_uploaded_at = request.user, timezone.now()
        with transaction.atomic():
            declaration.save()
            if old:
                transaction.on_commit(lambda: old[0].delete(old[1]))
        return Response(DeclarationSerializer(declaration).data)

    # ---------- helpers ----------

    @staticmethod
    def _declarations(app):
        return app.declarations.select_related('parent', 'application', 'physical_received_by').prefetch_related(
            'application__land_holdings')

    @staticmethod
    def _inspect(upload):
        try:
            return inspect_upload(upload)
        except ValidationError as exc:
            raise ValidationError({'file': exc.detail})

    def _editable_app(self):
        app = self.get_object()
        if not app.is_editable:
            raise PermissionDenied(LOCKED_MESSAGE)
        return app

    def _fresh(self, app):
        return self.get_queryset().get(pk=app.pk)


class DocumentDownloadView(APIView):
    """Streams a stored file after checking who is asking. Files are never exposed by a public URL."""

    permission_classes = [IsAuthenticated]

    def get(self, request, doc_id):
        doc = get_object_or_404(ApplicationDocument.objects.select_related('application'), pk=doc_id)
        is_owner = doc.application.student_id == request.user.pk
        if not is_owner and request.user.role not in DOCUMENT_REVIEWER_ROLES:
            raise NotFound()  # do not reveal that the file exists
        response = FileResponse(doc.file.open('rb'), content_type=doc.content_type,
                                filename=doc.original_name, as_attachment=False)
        response['Cache-Control'] = 'private, no-store'
        return response


def _can_review(user):
    return user.role in DOCUMENT_REVIEWER_ROLES


class DeclarationScanDownloadView(APIView):
    """Streams a Form 2 scan to its student or to reviewing staff."""

    permission_classes = [IsAuthenticated]

    def get(self, request, declaration_id):
        declaration = get_object_or_404(Declaration.objects.select_related('application'), pk=declaration_id)
        if declaration.application.student_id != request.user.pk and not _can_review(request.user):
            raise NotFound()
        if not declaration.scan:
            raise NotFound('No scan has been uploaded yet.')
        response = FileResponse(declaration.scan.open('rb'), content_type=declaration.scan_content_type,
                                filename=declaration.scan_original_name, as_attachment=False)
        response['Cache-Control'] = 'private, no-store'
        return response


class DeclarationReceiveView(APIView):
    """Placement Office records (POST) or undoes (DELETE) receipt of the original stamp paper."""

    permission_classes = [has_role(*DOCUMENT_REVIEWER_ROLES)]

    def _declaration(self, declaration_id):
        declaration = get_object_or_404(
            Declaration.objects.select_related('application', 'parent', 'physical_received_by'), pk=declaration_id)
        if declaration.application.status == ApplicationStatus.DRAFT:
            raise ValidationError({'detail': 'The application has not been submitted yet.'})
        return declaration

    def post(self, request, declaration_id):
        declaration = self._declaration(declaration_id)
        serializer = ReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        declaration.physical_received_on = serializer.validated_data.get('received_on', timezone.localdate())
        declaration.physical_received_by = request.user
        declaration.save(update_fields=['physical_received_on', 'physical_received_by'])
        return Response(DeclarationSerializer(declaration).data)

    def delete(self, request, declaration_id):
        declaration = self._declaration(declaration_id)
        declaration.physical_received_on = None
        declaration.physical_received_by = None
        declaration.save(update_fields=['physical_received_on', 'physical_received_by'])
        return Response(DeclarationSerializer(declaration).data)


class StaffApplicationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Placement Office review of submitted applications (drafts are not shown).

    Query parameters: cycle, department, status, complete (true/false), search (name, Registration ID,
    CNIC or email), ordering (submitted_at, -submitted_at, applicant_name)."""

    permission_classes = [has_role(*DOCUMENT_REVIEWER_ROLES)]
    ORDERINGS = {'submitted_at', '-submitted_at', 'applicant_name', '-applicant_name'}

    def get_serializer_class(self):
        return ReviewListSerializer if self.action == 'list' else StaffApplicationDetailSerializer

    def get_queryset(self):
        qs = (Application.objects.exclude(status=ApplicationStatus.DRAFT)
              .select_related('cycle', 'student__department', 'reviewed_by')
              .prefetch_related('declarations'))
        if self.action != 'list':
            return qs.prefetch_related(*DETAIL_PREFETCH, 'documents__uploaded_by')
        params = self.request.query_params
        if params.get('cycle'):
            qs = qs.filter(cycle_id=params['cycle'])
        if params.get('department'):
            qs = qs.filter(student__department_id=params['department'])
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('complete') in ('true', 'false'):
            # complete = every declaration has a scan and its original received
            qs = qs.annotate(open_declarations=Count('declarations', filter=Q(declarations__scan='') | Q(
                declarations__physical_received_on__isnull=True), distinct=True))
            qs = qs.filter(open_declarations=0) if params['complete'] == 'true' else qs.filter(open_declarations__gt=0)
        if search := params.get('search', '').strip():
            qs = qs.filter(Q(applicant_name__icontains=search) | Q(registration_id__icontains=search)
                           | Q(cnic__icontains=search) | Q(email__icontains=search)
                           | Q(student__email__icontains=search))
        ordering = params.get('ordering', '-submitted_at')
        return qs.order_by(ordering if ordering in self.ORDERINGS else '-submitted_at', 'pk')

    @action(detail=True, methods=['post'], url_path='status')
    def set_status(self, request, pk=None):
        """Set pending / under review / approved / rejected with remarks. Every change is recorded."""
        app = self.get_object()
        serializer = StatusUpdateSerializer(data=request.data, context={'application': app})
        serializer.is_valid(raise_exception=True)
        new_status, remarks = serializer.validated_data['status'], serializer.validated_data['remarks']
        with transaction.atomic():
            StatusChange.objects.create(application=app, from_status=app.status, to_status=new_status,
                                        remarks=remarks, changed_by=request.user)
            app.status, app.review_remarks = new_status, remarks
            app.reviewed_by, app.reviewed_at = request.user, timezone.now()
            app.save(update_fields=['status', 'review_remarks', 'reviewed_by', 'reviewed_at', 'updated_at'])
        return Response(StaffApplicationDetailSerializer(self.get_queryset().get(pk=app.pk)).data)
