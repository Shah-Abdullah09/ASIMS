from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'link', 'created_at', 'read_at']


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """The signed-in person's notifications, newest first (?unread=true for unread only)."""

    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)
        if self.request.query_params.get('unread') == 'true':
            qs = qs.filter(read_at__isnull=True)
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data['unread'] = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
        return response

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        note = self.get_object()
        if note.read_at is None:
            note.read_at = timezone.now()
            note.save(update_fields=['read_at'])
        return Response(NotificationSerializer(note).data)

    @action(detail=False, methods=['post'], url_path='read-all')
    def read_all(self, request):
        count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({'marked_read': count})
