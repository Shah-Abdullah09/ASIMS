from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import has_role
from apps.audit.log import record
from apps.audit.models import AuditAction
from apps.documents.validation import inspect_upload
from apps.workflow.engine import WorkflowError

from .access import PLACEMENT, STAFF_ROLES, can_open, visible_cases
from .checklist import build_checklist, max_files
from .choices import ApplicationStatus, DocumentReview
from .declarations import sync_declarations
from .models import Application, ApplicationDocument, Declaration, ScholarshipCycle, SectionFlag
from .serializers import (SECTIONS, ActionSerializer, ApplicationCreateSerializer, ApplicationDetailSerializer,
                          ApplicationListSerializer, CycleSerializer, DeclarationSerializer,
                          DocumentReplaceSerializer, DocumentReviewSerializer, DocumentSerializer,
                          DocumentUploadSerializer, FlagCreateSerializer, ForwardAllSerializer, InterviewSerializer,
                          ReceiveSerializer, ReviewListSerializer,
                          SectionFlagSerializer, StaffApplicationDetailSerializer, scan_upload_allowed)
from .submission import readiness
from .verification import section_unlocked, slot_unlocked
from .workflow import perform

DETAIL_PREFETCH = ['household_members', 'studying_members', 'parents', 'earning_members', 'asset_income',
                   'utility_months', 'vehicles', 'land_holdings', 'asset_worth', 'education_records',
                   'previous_scholarships', 'status_history__changed_by', 'flags__flagged_by',
                   'flags__resolved_by']


LOCKED_MESSAGE = 'This application has been submitted and can no longer be changed.'
SECTION_LOCKED = 'The Placement Office did not ask for changes to this section, so it stays as submitted.'
SLOT_LOCKED = 'The Placement Office did not ask for changes to this document, so it stays as submitted.'
VERIFIED_LOCKED = 'This file has been verified by the Placement Office and cannot be changed.'
CHANGEABLE = (ApplicationStatus.DRAFT, ApplicationStatus.RETURNED)


class StageConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'This case is no longer at Placement verification. Reload the page.'
    default_code = 'stage_conflict'

WORKFLOW_ERROR_STATUS = {'unknown_action': status.HTTP_400_BAD_REQUEST, 'forbidden': status.HTTP_403_FORBIDDEN,
                         'stage_conflict': status.HTTP_409_CONFLICT}


def run_action(app_id, action, user, request, **data):
    """Run a workflow action; returns an error Response, or None when it succeeded."""
    try:
        perform(app_id, action, user, request=request, **data)
    except WorkflowError as exc:
        return Response({'detail': exc.message, 'code': exc.code}, status=WORKFLOW_ERROR_STATUS[exc.code])
    return None


class OpenCycleListView(ListAPIView):
    """Scholarship cycles a student can apply to today."""

    permission_classes = [has_role(Role.STUDENT)]
    serializer_class = CycleSerializer
    pagination_class = None

    def get_queryset(self):
        today = timezone.localdate()
        return ScholarshipCycle.objects.filter(is_active=True, opens_on__lte=today, closes_on__gte=today)


class AllCycleListView(ListAPIView):
    """Every scholarship cycle, newest first, for the staff review filters."""

    permission_classes = [has_role(*STAFF_ROLES)]
    serializer_class = CycleSerializer
    pagination_class = None
    queryset = ScholarshipCycle.objects.all()


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
        record(AuditAction.APPLICATION_CREATED, request=request, target=app, cycle=app.cycle_id)
        return Response(ApplicationDetailSerializer(self._fresh(app)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path=r'sections/(?P<section>[a-z_]+)')
    def save_section(self, request, pk=None, section=None):
        """Save one wizard step as a draft."""
        serializer_class = SECTIONS.get(section)
        if serializer_class is None:
            raise NotFound(f'Unknown section "{section}". Valid sections: {", ".join(SECTIONS)}.')
        app = self._changeable_app()
        if not section_unlocked(app, section):
            raise PermissionDenied(SECTION_LOCKED)
        serializer = serializer_class(app, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record(AuditAction.APPLICATION_SAVED, request=request, target=app, section=section,
               fields=sorted(serializer.validated_data), stage=app.status)
        return Response(ApplicationDetailSerializer(self._fresh(app)).data)

    # ---------- documents ----------

    @action(detail=True, methods=['get', 'post'], url_path='documents')
    def documents(self, request, pk=None):
        """GET: the checklist with every slot, its rule and its files. POST: upload one file into a slot."""
        if request.method == 'GET':
            return Response(build_checklist(self.get_object(), DocumentSerializer))

        app = self._changeable_app()
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slot, upload = serializer.validated_data['slot'], serializer.validated_data['file']
        if not slot_unlocked(app, slot):
            raise PermissionDenied(SLOT_LOCKED)
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
        record(AuditAction.DOCUMENT_UPLOADED, request=request, target=doc, application=app.pk, slot=slot,
               name=doc.original_name, size=doc.size)
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put', 'delete'], url_path=r'documents/(?P<doc_id>\d+)')
    def document_detail(self, request, pk=None, doc_id=None):
        """PUT: replace the file in place (same slot). DELETE: remove it. Drafts, and the slots a returned
        application reopened (verified files excepted)."""
        app = self._changeable_app()
        doc = get_object_or_404(app.documents, pk=doc_id)
        if not slot_unlocked(app, doc.slot):
            raise PermissionDenied(SLOT_LOCKED)
        if app.status == ApplicationStatus.RETURNED and doc.review_status == DocumentReview.VERIFIED:
            raise PermissionDenied(VERIFIED_LOCKED)
        if request.method == 'DELETE':
            with transaction.atomic():
                record(AuditAction.DOCUMENT_DELETED, request=request, target=doc, application=app.pk, slot=doc.slot,
                       name=doc.original_name)
                doc.delete()
                transaction.on_commit(lambda name=doc.file.name, storage=doc.file.storage: storage.delete(name))
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = DocumentReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data['file']
        content_type, ext = self._inspect(upload)
        old_name, storage = doc.file.name, doc.file.storage
        replaced = doc.original_name
        doc.original_name = upload.name[:255]
        upload.name = stored_name(ext)
        doc.file = upload
        doc.content_type, doc.size = content_type, upload.size
        doc.uploaded_by, doc.uploaded_at = request.user, timezone.now()
        doc.clear_review()  # a new file has to be checked again
        with transaction.atomic():
            doc.save()
            record(AuditAction.DOCUMENT_REPLACED, request=request, target=doc, application=app.pk, slot=doc.slot,
                   name=doc.original_name, replaced=replaced)
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
            if error := run_action(app.pk, 'submit', request.user, request, remarks='Submitted by the student.'):
                transaction.set_rollback(True)
                return error
        app = self._fresh(app)
        self._send_confirmation(app)
        return Response(ApplicationDetailSerializer(self._fresh(app)).data)

    @action(detail=True, methods=['post'])
    def resubmit(self, request, pk=None):
        """Send a returned application back to the Placement Office after fixing what was flagged.
        Optional {remarks} tells the office what was changed."""
        app = self.get_object()
        if app.status != ApplicationStatus.RETURNED:
            raise PermissionDenied('Only an application returned to you can be resubmitted.')
        result = readiness(app)
        if not result['ready']:
            return Response({'detail': 'The application is not complete yet.', **result},
                            status=status.HTTP_400_BAD_REQUEST)
        remarks = str(request.data.get('remarks', '')).strip()[:2000] or 'Resubmitted by the student.'
        with transaction.atomic():
            sync_declarations(app)
            if error := run_action(app.pk, 'resubmit', request.user, request, remarks=remarks):
                transaction.set_rollback(True)
                return error
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
            record(AuditAction.SCAN_UPLOADED, request=request, target=declaration, application=app.pk,
                   name=declaration.scan_original_name, replaced=bool(old))
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

    def _changeable_app(self):
        """A draft, or an application returned for corrections (callers check which parts reopened)."""
        app = self.get_object()
        if app.status not in CHANGEABLE:
            raise PermissionDenied(LOCKED_MESSAGE)
        return app

    def _fresh(self, app):
        return self.get_queryset().get(pk=app.pk)


class DocumentDownloadView(APIView):
    """Streams a stored file after checking who is asking. Files are never exposed by a public URL."""

    permission_classes = [IsAuthenticated]

    def get(self, request, doc_id):
        doc = get_object_or_404(ApplicationDocument.objects.select_related('application'), pk=doc_id)
        if not can_open(request.user, doc.application):
            raise NotFound()  # do not reveal that the file exists
        response = FileResponse(doc.file.open('rb'), content_type=doc.content_type,
                                filename=doc.original_name, as_attachment=False)
        response['Cache-Control'] = 'private, no-store'
        return response


class DeclarationScanDownloadView(APIView):
    """Streams a Form 2 scan to its student or to reviewing staff."""

    permission_classes = [IsAuthenticated]

    def get(self, request, declaration_id):
        declaration = get_object_or_404(Declaration.objects.select_related('application'), pk=declaration_id)
        if not can_open(request.user, declaration.application):
            raise NotFound()
        if not declaration.scan:
            raise NotFound('No scan has been uploaded yet.')
        response = FileResponse(declaration.scan.open('rb'), content_type=declaration.scan_content_type,
                                filename=declaration.scan_original_name, as_attachment=False)
        response['Cache-Control'] = 'private, no-store'
        return response


class DeclarationReceiveView(APIView):
    """Placement Office records (POST) or undoes (DELETE) receipt of the original stamp paper."""

    permission_classes = [has_role(*PLACEMENT)]

    def _declaration(self, declaration_id):
        declaration = get_object_or_404(
            Declaration.objects.select_related('application', 'parent', 'physical_received_by'), pk=declaration_id)
        if declaration.application.status == ApplicationStatus.DRAFT:
            raise ValidationError({'detail': 'The application has not been submitted yet.'})
        if declaration.application.status not in (ApplicationStatus.PLACEMENT_VERIFICATION,
                                                  ApplicationStatus.RETURNED):
            raise ValidationError({'detail': 'The case has left Placement verification, so Form 2 receipts are final.'})
        return declaration

    def post(self, request, declaration_id):
        declaration = self._declaration(declaration_id)
        serializer = ReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        declaration.physical_received_on = serializer.validated_data.get('received_on', timezone.localdate())
        declaration.physical_received_by = request.user
        declaration.save(update_fields=['physical_received_on', 'physical_received_by'])
        record(AuditAction.ORIGINAL_RECEIVED, request=request, target=declaration,
               application=declaration.application_id, received_on=str(declaration.physical_received_on))
        return Response(DeclarationSerializer(declaration).data)

    def delete(self, request, declaration_id):
        declaration = self._declaration(declaration_id)
        declaration.physical_received_on = None
        declaration.physical_received_by = None
        declaration.save(update_fields=['physical_received_on', 'physical_received_by'])
        record(AuditAction.ORIGINAL_UNRECEIVED, request=request, target=declaration,
               application=declaration.application_id)
        return Response(DeclarationSerializer(declaration).data)


class StaffApplicationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Staff work on submitted applications: each role sees the cases access.visible_cases gives it.

    Query parameters: cycle, department, status, complete (true/false), search (name, Registration ID,
    CNIC or email), ordering (submitted_at, -submitted_at, applicant_name)."""

    permission_classes = [has_role(*STAFF_ROLES)]
    ORDERINGS = {'submitted_at', '-submitted_at', 'applicant_name', '-applicant_name'}

    def get_serializer_class(self):
        return ReviewListSerializer if self.action == 'list' else StaffApplicationDetailSerializer

    def get_queryset(self):
        qs = (visible_cases(self.request.user)
              .select_related('cycle', 'student__department', 'reviewed_by', 'interview_recorded_by')
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

    @action(detail=True, methods=['post'], url_path='actions')
    def take_action(self, request, pk=None):
        """Move the case along the approval chain: {action, remarks, percentage}. The detail lists the
        actions open to the current user in `available_actions`. Every action is recorded."""
        app = self.get_object()
        serializer = ActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if error := run_action(app.pk, data['action'], request.user, request, remarks=data['remarks'],
                                percentage=data['percentage']):
            return error
        detail = self.get_queryset().filter(pk=app.pk).first()
        if detail is None:
            # The case moved on out of this user's view (e.g. the DAC shortlisted it): confirm the new stage only
            app.refresh_from_db(fields=['status'])
            return Response({'id': app.pk, 'status': app.status, 'status_label': app.get_status_display(),
                             'left_queue': True, 'available_actions': []})
        return Response(self.get_serializer(detail).data)

    # ---------- Placement verification ----------

    def _placement_case(self, pk):
        """The case locked for a Placement verification change; only while it is at that stage."""
        if self.request.user.role not in PLACEMENT:
            raise PermissionDenied('Only the Placement Office can do this.')
        self.get_object()  # 404 for drafts and cases outside this user's view
        app = Application.objects.select_for_update().get(pk=pk)
        if app.status != ApplicationStatus.PLACEMENT_VERIFICATION:
            raise StageConflict()
        return app

    @action(detail=True, methods=['post'], url_path=r'documents/(?P<doc_id>\d+)/review')
    def review_document(self, request, pk=None, doc_id=None):
        """Mark one file Verified or Needs clarification (with a note the student sees)."""
        serializer = DocumentReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            app = self._placement_case(pk)
            doc = get_object_or_404(app.documents.select_related('uploaded_by'), pk=doc_id)
            doc.review_status = serializer.validated_data['review_status']
            doc.review_note = serializer.validated_data['note']
            doc.reviewed_by, doc.reviewed_at = request.user, timezone.now()
            doc.save(update_fields=['review_status', 'review_note', 'reviewed_by', 'reviewed_at'])
            record(AuditAction.DOCUMENT_REVIEWED, request=request, target=doc, application=app.pk, slot=doc.slot,
                   review_status=doc.review_status, note=doc.review_note)
        return Response(DocumentSerializer(doc).data)

    @action(detail=True, methods=['post'], url_path='flags')
    def add_flag(self, request, pk=None):
        """Flag a section for correction. Flagging an already flagged section updates its note."""
        serializer = FlagCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section, note = serializer.validated_data['section'], serializer.validated_data['note']
        with transaction.atomic():
            app = self._placement_case(pk)
            flag = app.flags.filter(section=section, resolved_at__isnull=True).first()
            if flag:
                flag.note, flag.flagged_by = note, request.user
                flag.save(update_fields=['note', 'flagged_by'])
            else:
                flag = SectionFlag.objects.create(application=app, section=section, note=note,
                                                  flagged_by=request.user)
            record(AuditAction.SECTION_FLAGGED, request=request, target=flag, application=app.pk, section=section,
                   note=note)
        return Response(SectionFlagSerializer(flag).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'flags/(?P<flag_id>\d+)')
    def clear_flag(self, request, pk=None, flag_id=None):
        """Withdraw an open flag (kept in the history as cleared)."""
        with transaction.atomic():
            app = self._placement_case(pk)
            flag = get_object_or_404(app.flags, pk=flag_id, resolved_at__isnull=True)
            flag.resolved_at, flag.resolved_by = timezone.now(), request.user
            flag.resolution = SectionFlag.CLEARED_BY_STAFF
            flag.save(update_fields=['resolved_at', 'resolved_by', 'resolution'])
            record(AuditAction.FLAG_CLEARED, request=request, target=flag, application=app.pk,
                   section=flag.section)
        return Response(SectionFlagSerializer(flag).data)

    # ---------- DAC ----------

    @action(detail=True, methods=['put'], url_path='interview')
    def interview(self, request, pk=None):
        """DAC member of the student's department records (or corrects) the interview at DAC review."""
        if request.user.role != Role.DAC_MEMBER:
            raise PermissionDenied('Only a DAC member records the interview.')
        serializer = InterviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.get_object()  # 404 unless the case is in this member's DAC queue
            app = Application.objects.select_for_update().get(pk=pk)
            if app.status != ApplicationStatus.DAC_REVIEW:
                raise StageConflict('This case is no longer at DAC review. Reload the page.')
            app.interview_date = serializer.validated_data['interview_date']
            app.interview_remarks = serializer.validated_data['interview_remarks']
            app.interview_recorded_by, app.interview_recorded_at = request.user, timezone.now()
            app.save(update_fields=['interview_date', 'interview_remarks', 'interview_recorded_by',
                                    'interview_recorded_at', 'updated_at'])
            record(AuditAction.INTERVIEW_RECORDED, request=request, target=app,
                   interview_date=str(app.interview_date), remarks=app.interview_remarks)
        return Response(self.get_serializer(self.get_queryset().get(pk=pk)).data)

    # ---------- forwarding ----------

    @action(detail=False, methods=['post'], url_path='forward-all')
    def forward_all(self, request):
        """Forward every case awaiting forwarding (optionally of one cycle) to the Director.
        Needs {"confirm": true}. Cases another person moved meanwhile are skipped and reported."""
        if request.user.role not in PLACEMENT:
            raise PermissionDenied('Only the Placement Office forwards cases.')
        serializer = ForwardAllSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        waiting = visible_cases(request.user).filter(status=ApplicationStatus.AWAITING_FORWARDING)
        if cycle := serializer.validated_data['cycle']:
            waiting = waiting.filter(cycle=cycle)
        forwarded, skipped = [], []
        for app_id in waiting.order_by('submitted_at', 'pk').values_list('pk', flat=True):
            error = run_action(app_id, 'forward', request.user, request, remarks='Forwarded with all shortlisted cases.')
            (skipped if error else forwarded).append(app_id)
        return Response({'forwarded': forwarded, 'skipped': skipped})
