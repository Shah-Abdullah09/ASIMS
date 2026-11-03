from django.contrib import admin

from .models import InternshipRequest, InternshipStatusChange


class HistoryInline(admin.TabularInline):
    model = InternshipStatusChange
    extra = 0
    can_delete = False
    fields = readonly_fields = ['from_status', 'to_status', 'action', 'remarks', 'changed_by', 'role', 'changed_at']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(InternshipRequest)
class InternshipRequestAdmin(admin.ModelAdmin):
    """Shown for reference; the chain moves a request (history, audit, notifications), so the stage is read-only."""
    list_display = ['id', 'student', 'organisation', 'status', 'start_date', 'end_date', 'submitted_at']
    list_filter = ['status', 'mode']
    search_fields = ['student__email', 'student__full_name', 'organisation']
    readonly_fields = ['student', 'status', 'submitted_at', 'faculty_supervisor', 'letter_reference', 'issued_on']
    inlines = [HistoryInline]
