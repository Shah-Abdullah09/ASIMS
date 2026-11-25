from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.models import PLACEMENT_ROLES, Role
from apps.accounts.permissions import has_role
from apps.audit.log import record
from apps.audit.models import AuditAction
from apps.workflow.views import run_action

from .choices import InternshipStatus
from .models import Company, Internship
from .serializers import CompanySerializer, InternshipSerializer, SubmitSerializer
from .workflow import RUNNER

EDITABLE = (InternshipStatus.DRAFT, InternshipStatus.RETURNED)


class StudentInternshipViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                               mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """A student's own internship requests. Other students' requests are invisible (404)."""

    queryset = Internship.objects.none()  # for the API schema; get_queryset limits it to the student
    permission_classes = [has_role(Role.STUDENT)]
    serializer_class = InternshipSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return (Internship.objects.filter(student=self.request.user).select_related('program', 'company')
                .prefetch_related('status_history__changed_by'))

    def perform_create(self, serializer):
        internship = serializer.save()
        record(AuditAction.INTERNSHIP_CREATED, request=self.request, target=internship)

    def perform_update(self, serializer):
        if serializer.instance.status not in EDITABLE:
            raise ValidationError({'detail': 'This request has been submitted and can no longer be changed.'})
        serializer.save()
        record(AuditAction.INTERNSHIP_SAVED, request=self.request, target=serializer.instance,
               fields=sorted(serializer.validated_data))

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Send the request to the DIC: the first time, or again after it was returned."""
        internship = self.get_object()
        serializer = SubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        step = 'resubmit' if internship.status == InternshipStatus.RETURNED else 'submit'
        if error := run_action(RUNNER, internship.pk, step, request.user, request,
                               remarks=serializer.validated_data['remarks']):
            return error
        return Response(self.get_serializer(self.get_object()).data)


class CompanyViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):
    """The shared list of companies (?search= by name). Students and staff add companies; the Placement Office
    corrects them."""

    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    pagination_class = None
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        roles = PLACEMENT_ROLES if self.action == 'partial_update' else (Role.STUDENT, Role.DIC, *PLACEMENT_ROLES)
        return [has_role(*roles)()]

    def get_queryset(self):
        if search := self.request.query_params.get('search', '').strip():
            return self.queryset.filter(name__icontains=search)
        return self.queryset

    def perform_create(self, serializer):
        company = serializer.save(added_by=self.request.user)
        record(AuditAction.COMPANY_CHANGED, request=self.request, target=company, change='created', name=company.name)

    def perform_update(self, serializer):
        company = serializer.save()
        record(AuditAction.COMPANY_CHANGED, request=self.request, target=company, change='updated',
               fields=sorted(serializer.validated_data))
