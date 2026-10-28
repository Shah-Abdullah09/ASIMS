from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Browse and search only; nobody can add, change or delete entries."""

    list_display = ['created_at', 'actor', 'actor_role', 'action', 'target_type', 'target_id', 'ip_address']
    list_filter = ['action', 'actor_role', 'target_type']
    search_fields = ['actor__email', 'actor__full_name', 'target_id']
    date_hierarchy = 'created_at'
    list_select_related = ['actor']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
