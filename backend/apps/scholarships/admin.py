from django.contrib import admin

from .models import (Application, ApplicationDocument, AssetIncome, AssetWorth, Declaration, EarningMember,
                     EducationRecord, HouseholdMember, LandHolding, ParentGuardian, PreviousScholarship,
                     ScholarshipCycle, StatusChange, StudyingMember, UtilityMonth, Vehicle)


@admin.register(ScholarshipCycle)
class ScholarshipCycleAdmin(admin.ModelAdmin):
    list_display = ['name', 'opens_on', 'closes_on', 'is_active']
    list_filter = ['is_active']


class ReadOnlyFileInline(admin.TabularInline):
    """Files are uploaded by students through the API, not through the admin."""
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class DocumentInline(ReadOnlyFileInline):
    model = ApplicationDocument
    fields = readonly_fields = ['slot', 'original_name', 'content_type', 'size', 'uploaded_by', 'uploaded_at']


class StatusHistoryInline(ReadOnlyFileInline):
    model = StatusChange
    fields = readonly_fields = ['from_status', 'to_status', 'remarks', 'changed_by', 'changed_at']


class DeclarationInline(ReadOnlyFileInline):
    model = Declaration
    fields = ['parent', 'scan_original_name', 'scan_uploaded_at', 'physical_received_on', 'physical_received_by']
    readonly_fields = ['parent', 'scan_original_name', 'scan_uploaded_at']


def tabular(model_class):
    return type(f'{model_class.__name__}Inline', (admin.TabularInline,), {'model': model_class, 'extra': 0})


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['id', 'applicant_name', 'registration_id', 'cycle', 'student_department', 'status',
                    'submitted_at']
    list_filter = ['cycle', 'status', 'student__department']
    search_fields = ['applicant_name', 'registration_id', 'cnic', 'student__email']
    readonly_fields = ['student', 'created_at', 'updated_at', 'submitted_at', 'age']
    list_select_related = ['cycle', 'student__department']
    inlines = [tabular(m) for m in (HouseholdMember, EarningMember, StudyingMember, ParentGuardian, AssetIncome,
                                    UtilityMonth, Vehicle, LandHolding, AssetWorth, EducationRecord,
                                    PreviousScholarship)] + [DocumentInline, DeclarationInline, StatusHistoryInline]

    @admin.display(description='Department', ordering='student__department__name')
    def student_department(self, obj):
        return obj.student.department
