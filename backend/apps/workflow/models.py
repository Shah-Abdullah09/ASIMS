from django.conf import settings
from django.db import models


class StatusChangeBase(models.Model):
    """One move along a chain: who took which action, from which stage to which, and why. Each chain adds the link
    to its case and gives from_status and to_status its own stage choices."""
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    action = models.CharField(max_length=30, blank=True, help_text='Workflow action, e.g. verify or approve')
    remarks = models.TextField(blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    role = models.CharField(max_length=30, blank=True, help_text='Role of the person at the time of the action')
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['changed_at', 'pk']
