from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.audit.log import record
from apps.audit.models import AuditAction

from .models import Department, User
from .passwords import INVITE, send_password_link


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['email']
    list_display = ['email', 'full_name', 'registration_id', 'role', 'department', 'is_active', 'is_email_verified']
    list_filter = ['role', 'is_active', 'is_email_verified']
    search_fields = ['email', 'full_name', 'registration_id']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile', {'fields': ('full_name', 'registration_id', 'role', 'department', 'is_email_verified')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'full_name', 'role', 'password1', 'password2')}),
    )
    actions = ['send_invitation']

    @admin.action(description='Send set-password invitation (email link)')
    def send_invitation(self, request, queryset):
        sent = 0
        for user in queryset.filter(is_active=True):
            send_password_link(user, INVITE)
            record(AuditAction.INVITATION_SENT, request=request, target=user, email=user.email)
            sent += 1
        self.message_user(request, f'Invitation sent to {sent} account(s). Inactive accounts were skipped.')


admin.site.register(Department)
