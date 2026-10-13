from django.db import transaction
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
from .models import Application, ApplicationDocument, ScholarshipCycle
from .serializers import (SECTIONS, ApplicationCreateSerializer, ApplicationDetailSerializer,
                          ApplicationListSerializer, CycleSerializer, DocumentReplaceSerializer,
                          DocumentSerializer, DocumentUploadSerializer)

DETAIL_PREFETCH = ['household_members', 'studying_members', 'parents', 'earning_members', 'asset_income',
                   'utility_months', 'vehicles', 'land_holdings', 'asset_worth', 'education_records',
                   'previous_scholarships']

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

    # ---------- helpers ----------

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
