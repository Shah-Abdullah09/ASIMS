from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
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

from .access import can_open
from .models import CLOSED, InternshipRequest
from .serializers import ActionSerializer, RequestDetailSerializer, StudentRequestSerializer, readiness
from .workflow import perform

ERROR_STATUS = {'unknown_action': status.HTTP_400_BAD_REQUEST, 'forbidden': status.HTTP_403_FORBIDDEN,
                'stage_conflict': status.HTTP_409_CONFLICT}
LOCKED = 'This request has been submitted and can no longer be changed.'
STUDENT_ACTIONS = {'submit', 'resubmit', 'withdraw'}


def run_action(req_id, action, user, request, remarks=''):
    """Run a chain action; returns an error Response, or None when it succeeded."""
    try:
        perform(req_id, action, user, remarks=remarks, request=request)
    except WorkflowError as exc:
        return Response({'detail': exc.message, 'code': exc.code}, status=ERROR_STATUS[exc.code])
    return None


class StudentRequestViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                            mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """A student's own internship requests: fill in a draft, attach an offer letter, submit, follow the stages."""

    permission_classes = [has_role(Role.STUDENT)]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = InternshipRequest.objects.none()  # for the API schema
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        return (InternshipRequest.objects.filter(student=self.request.user)
                .select_related('student__department', 'faculty_supervisor')
                .prefetch_related('status_history__changed_by'))

    def get_serializer_class(self):
        return StudentRequestSerializer if self.action in ('create', 'partial_update') else RequestDetailSerializer

    def _detail(self, req, code=status.HTTP_200_OK):
        return Response(RequestDetailSerializer(self.get_queryset().get(pk=req.pk),
                                                context=self.get_serializer_context()).data, status=code)

    def create(self, request, *args, **kwargs):
        if self.get_queryset().exclude(status__in=CLOSED).exists():
            raise ValidationError({'detail': 'You already have an open internship request. Finish or withdraw it '
                                             'before starting another.'})
        serializer = StudentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        req = serializer.save(student=request.user)
        record(AuditAction.APPLICATION_CREATED, request=request, target=req, kind='internship')
        return self._detail(req, status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        req = self._editable()
        serializer = StudentRequestSerializer(req, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record(AuditAction.APPLICATION_SAVED, request=request, target=req, kind='internship',
               fields=sorted(serializer.validated_data))
        return self._detail(req)

    @action(detail=True, methods=['get'])
    def readiness(self, request, pk=None):
        return Response(readiness(self.get_object()))

    @action(detail=True, methods=['post', 'delete'], url_path='offer-letter')
    def offer_letter(self, request, pk=None):
        """Attach (or replace) the optional offer letter or organisation email; DELETE removes it."""
        req = self._editable()
        old = (req.offer_letter.storage, req.offer_letter.name) if req.offer_letter else None
        if request.method == 'DELETE':
            req.offer_letter, req.offer_letter_name, req.offer_letter_type, req.offer_letter_size = '', '', '', None
        else:
            upload = request.FILES.get('file')
            if upload is None:
                raise ValidationError({'file': 'Choose a file to upload.'})
            try:
                content_type, ext = inspect_upload(upload)
            except ValidationError as exc:
                raise ValidationError({'file': exc.detail})
            req.offer_letter_name, req.offer_letter_type, req.offer_letter_size = upload.name[:255], content_type, upload.size
            upload.name = f'offer.{ext}'
            req.offer_letter = upload
        with transaction.atomic():
            req.save()
            record(AuditAction.DOCUMENT_UPLOADED if request.method == 'POST' else AuditAction.DOCUMENT_DELETED,
                   request=request, target=req, kind='internship offer letter', name=req.offer_letter_name)
            if old:
                transaction.on_commit(lambda: old[0].delete(old[1]))
        return self._detail(req)

    @action(detail=True, methods=['post'])
    def actions(self, request, pk=None):
        """Submit, resubmit (after a return) or withdraw. Submitting checks the request is complete."""
        req = self.get_object()
        serializer = ActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data['action']
        if name not in STUDENT_ACTIONS:
            raise PermissionDenied('Students can submit, resubmit or withdraw.')
        if name in ('submit', 'resubmit'):
            result = readiness(req)
            if not result['ready']:
                return Response({'detail': 'The request is not complete yet.', **result},
                                status=status.HTTP_400_BAD_REQUEST)
        if error := run_action(req.pk, name, request.user, request, serializer.validated_data['remarks']):
            return error
        return self._detail(req)

    def _editable(self):
        req = self.get_object()
        if not req.is_editable:
            raise PermissionDenied(LOCKED)
        return req


class InternshipFileView(APIView):
    """The offer letter or the issued internship letter, for the student and staff who can open the request."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={(200, '*/*'): OpenApiTypes.BINARY})
    def get(self, request, req_id, kind):
        req = get_object_or_404(InternshipRequest.objects.select_related('student'), pk=req_id)
        if not can_open(request.user, req):
            raise NotFound()
        if kind == 'offer-letter' and req.offer_letter:
            file, content_type, name = req.offer_letter, req.offer_letter_type, req.offer_letter_name
        elif kind == 'letter' and req.letter_pdf:
            file, content_type, name = req.letter_pdf, 'application/pdf', f'internship-letter-{req.pk}.pdf'
        else:
            raise NotFound()
        response = FileResponse(file.open('rb'), content_type=content_type, filename=name, as_attachment=False)
        response['Cache-Control'] = 'private, no-store'
        return response
