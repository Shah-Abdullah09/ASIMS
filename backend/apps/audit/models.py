"""An append-only record of who did what and when, kept apart from the business tables.

Entries can be added but never changed or deleted through the application (the admin is read-only too)."""
from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    LOGIN = 'login', 'Logged in'
    LOGIN_FAILED = 'login_failed', 'Login failed'
    REGISTER = 'register', 'Registered'
    VERIFY_EMAIL = 'verify_email', 'Verified email'
    USER_CREATED = 'user_created', 'Account created'
    USER_UPDATED = 'user_updated', 'Account changed'
    DEPARTMENT_CHANGED = 'department_changed', 'Department added or changed'
    APPLICATION_CREATED = 'application_created', 'Application started'
    APPLICATION_SAVED = 'application_saved', 'Application section saved'
    DOCUMENT_UPLOADED = 'document_uploaded', 'Document uploaded'
    DOCUMENT_REPLACED = 'document_replaced', 'Document replaced'
    DOCUMENT_DELETED = 'document_deleted', 'Document deleted'
    SCAN_UPLOADED = 'scan_uploaded', 'Form 2 scan uploaded'
    ORIGINAL_RECEIVED = 'original_received', 'Form 2 original received'
    ORIGINAL_UNRECEIVED = 'original_unreceived', 'Form 2 receipt undone'
    DOCUMENT_REVIEWED = 'document_reviewed', 'Document reviewed'
    SECTION_FLAGGED = 'section_flagged', 'Section flagged'
    FLAG_CLEARED = 'flag_cleared', 'Flag cleared'
    WORKFLOW_ACTION = 'workflow_action', 'Workflow action'


class AuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError('Audit log entries cannot be changed.')

    def delete(self):
        raise PermissionError('Audit log entries cannot be deleted.')


class AuditLog(models.Model):
    # Empty for a failed login with an unknown email
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                              related_name='audit_entries')
    actor_role = models.CharField(max_length=30, blank=True, help_text='Role at the time of the action')
    action = models.CharField(max_length=30, choices=AuditAction.choices)
    target_type = models.CharField(max_length=50, blank=True, help_text='e.g. scholarships.application')
    target_id = models.CharField(max_length=40, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AuditQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['target_type', 'target_id'])]

    def __str__(self):
        who = self.actor.email if self.actor_id else 'anonymous'
        return f'{self.created_at:%Y-%m-%d %H:%M} {who} {self.get_action_display()}'

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionError('Audit log entries cannot be changed.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError('Audit log entries cannot be deleted.')
