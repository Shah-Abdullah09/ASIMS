from django.contrib import admin

from .models import (Application, ApplicationDocument, AssetIncome, AssetWorth, AwardLetter, Declaration,
                     EarningMember, EducationRecord, FeeAdjustment, HouseholdMember, LandHolding, ParentGuardian,
                     PreviousScholarship, ScholarshipCycle, SectionFlag, StatusChange, StudyingMember, UtilityMonth,
                     Vehicle)


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
    fields = readonly_fields = ['slot', 'original_name', 'content_type', 'size', 'uploaded_by', 'uploaded_at',
                                'review_status', 'review_note', 'reviewed_by', 'reviewed_at']


class StatusHistoryInline(ReadOnlyFileInline):
    model = StatusChange
    fields = readonly_fields = ['from_status', 'to_status', 'action', 'remarks', 'percentage', 'changed_by', 'role',
                                'changed_at']


class DeclarationInline(ReadOnlyFileInline):
    model = Declaration
    # Receipts are recorded in the app, where the stage is checked and the change audited
    fields = readonly_fields = ['parent', 'scan_original_name', 'scan_uploaded_at', 'physical_received_on',
                                'physical_received_by']


class FlagInline(ReadOnlyFileInline):
    model = SectionFlag
    fields = readonly_fields = ['section', 'note', 'flagged_by', 'flagged_at', 'resolved_at', 'resolved_by',
                                'resolution']


def tabular(model_class):
    return type(f'{model_class.__name__}Inline', (admin.TabularInline,), {'model': model_class, 'extra': 0})


class AwardLetterInline(ReadOnlyFileInline):
    model = AwardLetter
    fields = readonly_fields = ['reference', 'issued_on', 'percentage', 'generated_at', 'signed_issued_on',
                                'signed_marked_by', 'signed_scan_original_name', 'signed_scan_uploaded_at']


class FeeAdjustmentInline(ReadOnlyFileInline):
    model = FeeAdjustment
    fields = readonly_fields = ['semester_fee', 'percentage', 'scholarship_amount', 'fee_payable', 'voucher_number',
                                'adjusted_on', 'remarks', 'recorded_by', 'recorded_at']


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['id', 'applicant_name', 'registration_id', 'cycle', 'student_department', 'status',
                    'submitted_at']
    list_filter = ['cycle', 'status', 'student__department']
    search_fields = ['applicant_name', 'registration_id', 'cnic', 'student__email']
    # The approval chain moves a case (history, audit, emails); the admin only shows where it stands
    readonly_fields = ['student', 'created_at', 'updated_at', 'submitted_at', 'age', 'status', 'scholarship_percentage',
                       'review_remarks', 'reviewed_by', 'reviewed_at', 'interview_date', 'interview_remarks',
                       'interview_recorded_by', 'interview_recorded_at']
    list_select_related = ['cycle', 'student__department']
    inlines = [tabular(m) for m in (HouseholdMember, EarningMember, StudyingMember, ParentGuardian, AssetIncome,
                                    UtilityMonth, Vehicle, LandHolding, AssetWorth, EducationRecord,
                                    PreviousScholarship)] + [DocumentInline, DeclarationInline, FlagInline,
                                                             AwardLetterInline, FeeAdjustmentInline,
                                                             StatusHistoryInline]

    @admin.display(description='Department', ordering='student__department__name')
    def student_department(self, obj):
        return obj.student.department
