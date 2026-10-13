from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import has_role

from .models import Application, ScholarshipCycle
from .serializers import (SECTIONS, ApplicationCreateSerializer, ApplicationDetailSerializer,
                          ApplicationListSerializer, CycleSerializer)

DETAIL_PREFETCH = ['household_members', 'studying_members', 'parents', 'earning_members', 'asset_income',
                   'utility_months', 'vehicles', 'land_holdings', 'asset_worth', 'education_records',
                   'previous_scholarships']


class OpenCycleListView(ListAPIView):
    """Scholarship cycles a student can apply to today."""

    permission_classes = [has_role(Role.STUDENT)]
    serializer_class = CycleSerializer
    pagination_class = None

    def get_queryset(self):
        today = timezone.localdate()
        return ScholarshipCycle.objects.filter(is_active=True, opens_on__lte=today, closes_on__gte=today)


class StudentApplicationViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                                viewsets.GenericViewSet):
    """A student's own applications. Other students' applications are invisible (404)."""

    permission_classes = [has_role(Role.STUDENT)]

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
        app = self.get_object()
        if not app.is_editable:
            raise PermissionDenied('This application has been submitted and can no longer be changed.')
        serializer = serializer_class(app, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ApplicationDetailSerializer(self._fresh(app)).data)

    def _fresh(self, app):
        return self.get_queryset().get(pk=app.pk)
