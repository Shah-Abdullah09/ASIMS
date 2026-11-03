from django.db.models import Q
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import has_role

from .models import AuditAction, AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source='actor.email', default=None, read_only=True)
    actor_name = serializers.CharField(source='actor.full_name', default=None, read_only=True)
    action_label = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'created_at', 'actor', 'actor_name', 'actor_role', 'action', 'action_label', 'target_type',
                  'target_id', 'details', 'ip_address']


class AuditLogListView(ListAPIView):
    """The audit log for the Administrator, newest first. Filters: ?action=, ?actor= (email or name),
    ?date_from=, ?date_to= (YYYY-MM-DD), ?target_type= and ?target_id=. Read-only."""

    permission_classes = [has_role(Role.ADMINISTRATOR)]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        qs = AuditLog.objects.select_related('actor')
        params = self.request.query_params
        if params.get('action'):
            qs = qs.filter(action=params['action'])
        if actor := params.get('actor', '').strip():
            qs = qs.filter(Q(actor__email__icontains=actor) | Q(actor__full_name__icontains=actor))
        if (day := parse_date(params.get('date_from', '') or '')):
            qs = qs.filter(created_at__date__gte=day)
        if (day := parse_date(params.get('date_to', '') or '')):
            qs = qs.filter(created_at__date__lte=day)
        if params.get('target_type'):
            qs = qs.filter(target_type=params['target_type'])
        if params.get('target_id'):
            qs = qs.filter(target_id=params['target_id'])
        return qs.order_by('-created_at', '-pk')


class AuditActionListView(APIView):
    """The action names for the filter."""

    permission_classes = [has_role(Role.ADMINISTRATOR)]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response([{'value': value, 'label': label} for value, label in AuditAction.choices])
