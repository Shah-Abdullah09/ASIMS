"""API shapes for the scholarship application.

The form is saved section by section (one wizard step at a time). Each section only checks
formats and consistency, so incomplete drafts can be saved; "required" rules are checked on submit.
Lists inside a section (family members, vehicles, ...) are replaced as a whole on each save."""
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from . import models as m
from .choices import ApplicationStatus
from .calculations import summarize
from .declarations import render, sync_declarations
from .submission import completion
from .validators import cnic_validator, landline_validator, mobile_validator


# ---------- normalising fields ----------

class CnicField(serializers.CharField):
    """Accepts 13 digits with or without dashes; stores 12345-1234567-1."""

    def __init__(self, **kwargs):
        kwargs.setdefault('allow_blank', True)
        kwargs.setdefault('required', False)
        super().__init__(max_length=15, validators=[cnic_validator], **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        digits = re.sub(r'[\s-]', '', value)
        if re.fullmatch(r'\d{13}', digits):
            return f'{digits[:5]}-{digits[5:12]}-{digits[12]}'
        return value


class PhoneField(serializers.CharField):
    """Ignores spaces and dashes people type in phone numbers."""

    def __init__(self, validator, max_length, **kwargs):
        super().__init__(max_length=max_length, validators=[validator], allow_blank=True, required=False, **kwargs)

    def to_internal_value(self, data):
        return re.sub(r'[\s-]', '', super().to_internal_value(data))


def run_model_clean(model_class, attrs):
    """Apply the model's own cross-field rules (e.g. net pay not above gross) to incoming data."""
    try:
        model_class(**attrs).clean()
    except DjangoValidationError as exc:
        raise serializers.ValidationError(serializers.as_serializer_error(exc))
    return attrs


def unique_rows(rows, key, label):
    seen = [r[key] for r in rows]
    if len(seen) != len(set(seen)):
        raise serializers.ValidationError(f'Each {label} can only appear once.')
    return rows


# ---------- child rows ----------

class ChildSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        return run_model_clean(self.Meta.model, attrs)


def child(model_class, extra_fields=None):
    meta = type('Meta', (), {'model': model_class, 'exclude': ['application'], 'read_only_fields': ['id']})
    return type(f'{model_class.__name__}Serializer', (ChildSerializer,), {'Meta': meta, **(extra_fields or {})})


HouseholdMemberSerializer = child(m.HouseholdMember)
EarningMemberSerializer = child(m.EarningMember)
StudyingMemberSerializer = child(m.StudyingMember)
AssetIncomeSerializer = child(m.AssetIncome)
UtilityMonthSerializer = child(m.UtilityMonth)
VehicleSerializer = child(m.Vehicle)
LandHoldingSerializer = child(m.LandHolding)
AssetWorthSerializer = child(m.AssetWorth)
EducationRecordSerializer = child(m.EducationRecord)
PreviousScholarshipSerializer = child(m.PreviousScholarship)
ParentGuardianSerializer = child(m.ParentGuardian, {
    'cnic': CnicField(),
    'mobile': PhoneField(mobile_validator, 13),
    'tel_office': PhoneField(landline_validator, 11),
})

# section field name -> (related name on Application, serializer, key that must be unique, label)
NESTED = {
    'household_members': (HouseholdMemberSerializer, None, None),
    'studying_members': (StudyingMemberSerializer, None, None),
    'parents': (ParentGuardianSerializer, 'role', 'parent / guardian role'),
    'earning_members': (EarningMemberSerializer, None, None),
    'asset_income': (AssetIncomeSerializer, 'source', 'income source'),
    'utility_months': (UtilityMonthSerializer, 'month_index', 'month'),
    'vehicles': (VehicleSerializer, None, None),
    'land_holdings': (LandHoldingSerializer, 'category', 'land category'),
    'asset_worth': (AssetWorthSerializer, 'title', 'asset title'),
    'education_records': (EducationRecordSerializer, 'level', 'education level'),
    'previous_scholarships': (PreviousScholarshipSerializer, None, None),
}


# ---------- sections ----------

class SectionSerializer(serializers.ModelSerializer):
    """Base for one wizard step. Scalar fields are set directly; nested lists are replaced."""

    class Meta:
        model = m.Application
        fields = []
        validators = []  # uniqueness is checked explicitly where needed

    def get_fields(self):
        fields = super().get_fields()
        for name, field in fields.items():
            field.required = False
        return fields

    def validate(self, attrs):
        for name, (_, key, label) in NESTED.items():
            if name in attrs and key:
                unique_rows(attrs[name], key, label)
        return attrs

    @transaction.atomic
    def update(self, instance, validated):
        nested = {k: validated.pop(k) for k in list(validated) if k in NESTED}
        for field, value in validated.items():
            setattr(instance, field, value)
        instance.save()
        for name, rows in nested.items():
            model_class = NESTED[name][0].Meta.model
            getattr(instance, name).all().delete()
            model_class.objects.bulk_create(model_class(application=instance, **row) for row in rows)
        sync_declarations(instance)
        return instance


def nested(name):
    return NESTED[name][0](many=True, required=False)


class PersonalSection(SectionSerializer):
    cnic = CnicField()
    mobile = PhoneField(mobile_validator, 13)
    tel_residence = PhoneField(landline_validator, 11)
    registration_id = serializers.RegexField(r'^\d{6,8}$', required=False, allow_blank=True,
                                             error_messages={'invalid': 'Registration ID must be 6 to 8 digits.'})

    class Meta(SectionSerializer.Meta):
        fields = ['registration_id', 'program', 'applicant_name', 'gender', 'marital_status', 'cnic',
                  'date_of_birth', 'domicile', 'present_address', 'permanent_address', 'tel_residence', 'mobile']

    def validate_cnic(self, value):
        app = self.instance
        if value and m.Application.objects.filter(cycle=app.cycle, cnic=value).exclude(pk=app.pk).exists():
            raise serializers.ValidationError('This CNIC is already used on another application in this cycle.')
        return value

    def validate_date_of_birth(self, value):
        if value:
            today = timezone.localdate()
            age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
            if not 15 <= age <= 60:
                raise serializers.ValidationError('Age must be between 15 and 60 years.')
        return value


class HouseholdSection(SectionSerializer):
    household_members = nested('household_members')
    studying_members = nested('studying_members')

    class Meta(SectionSerializer.Meta):
        fields = ['total_family_members', 'household_members', 'studying_members']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        total = attrs.get('total_family_members', self.instance.total_family_members)
        members = attrs.get('household_members')
        if total and members is not None and len(members) > total:
            raise serializers.ValidationError(
                {'household_members': f'You listed {len(members)} members but said {total} live with you.'})
        return attrs


class ParentsSection(SectionSerializer):
    parents = nested('parents')

    class Meta(SectionSerializer.Meta):
        fields = ['parents']

    @transaction.atomic
    def update(self, instance, validated):
        """Update father / mother / guardian in place (matched by role) so their Form 2
        declarations and uploaded scans survive re-saving this step."""
        rows = validated.pop('parents', None)
        if rows is not None:
            keep = []
            for row in rows:
                parent, _ = m.ParentGuardian.objects.update_or_create(
                    application=instance, role=row['role'], defaults=row)
                keep.append(parent.pk)
            for parent in instance.parents.exclude(pk__in=keep):
                declaration = getattr(parent, 'declaration', None)
                if declaration and declaration.scan:
                    name, storage = declaration.scan.name, declaration.scan.storage
                    transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
                parent.delete()
        return super().update(instance, validated)


class IncomeSection(SectionSerializer):
    earning_members = nested('earning_members')
    asset_income = nested('asset_income')

    class Meta(SectionSerializer.Meta):
        fields = ['applicant_gross_income', 'applicant_net_income', 'earning_members', 'asset_income',
                  'asset_income_other_specify']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        gross = attrs.get('applicant_gross_income', self.instance.applicant_gross_income)
        net = attrs.get('applicant_net_income', self.instance.applicant_net_income)
        if gross is not None and net is not None and net > gross:
            raise serializers.ValidationError({'applicant_net_income': 'Net pay cannot be more than gross pay.'})
        return attrs


class AccommodationSection(SectionSerializer):
    class Meta(SectionSerializer.Meta):
        fields = ['accommodation_type', 'accommodation_status', 'rent_paid_by', 'plot_size_sqft',
                  'covered_area_sqft', 'accommodation_address', 'bedrooms', 'air_conditioners', 'monthly_rent',
                  'other_house_owned', 'other_house_details']


class ExpensesSection(SectionSerializer):
    utility_months = nested('utility_months')

    class Meta(SectionSerializer.Meta):
        fields = ['utility_months', 'medical_monthly', 'misc_monthly', 'negative_income_explanation']


class AssetsSection(SectionSerializer):
    vehicles = nested('vehicles')
    land_holdings = nested('land_holdings')
    asset_worth = nested('asset_worth')

    class Meta(SectionSerializer.Meta):
        fields = ['owns_transport', 'vehicles', 'cattle_count', 'cattle_kind', 'land_holdings', 'asset_worth',
                  'education_loan', 'education_loan_details', 'other_financing', 'admission_fee_paid_how']


class EducationSection(SectionSerializer):
    education_records = nested('education_records')
    previous_scholarships = nested('previous_scholarships')
    statement_of_purpose = serializers.CharField(max_length=3000, required=False, allow_blank=True)

    class Meta(SectionSerializer.Meta):
        fields = ['education_records', 'last_institution_monthly_fee', 'other_scholarships',
                  'previous_scholarships', 'statement_of_purpose']


class UndertakingSection(SectionSerializer):
    class Meta(SectionSerializer.Meta):
        fields = ['undertaking_accepted', 'undertaking_name']

    def update(self, instance, validated):
        accepted = validated.get('undertaking_accepted', instance.undertaking_accepted)
        validated['undertaking_date'] = timezone.localdate() if accepted else None
        return super().update(instance, validated)


SECTIONS = {
    'personal': PersonalSection,
    'household': HouseholdSection,
    'parents': ParentsSection,
    'income': IncomeSection,
    'accommodation': AccommodationSection,
    'expenses': ExpensesSection,
    'assets': AssetsSection,
    'education': EducationSection,
    'undertaking': UndertakingSection,
}


# ---------- whole application ----------

class CycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.ScholarshipCycle
        fields = ['id', 'name', 'opens_on', 'closes_on']


class ApplicationListSerializer(serializers.ModelSerializer):
    cycle_name = serializers.CharField(source='cycle.name', read_only=True)

    class Meta:
        model = m.Application
        fields = ['id', 'cycle', 'cycle_name', 'status', 'applicant_name', 'registration_id', 'submitted_at',
                  'updated_at']


class ApplicationCreateSerializer(serializers.Serializer):
    cycle = serializers.PrimaryKeyRelatedField(queryset=m.ScholarshipCycle.objects.all())

    def validate_cycle(self, cycle):
        if not cycle.is_open():
            raise serializers.ValidationError('This scholarship cycle is not open for applications.')
        if m.Application.objects.filter(cycle=cycle, student=self.context['request'].user).exists():
            raise serializers.ValidationError('You already have an application for this cycle.')
        return cycle

    def create(self, validated):
        student = self.context['request'].user
        # Prefill what the system already knows about the student
        return m.Application.objects.create(
            cycle=validated['cycle'], student=student, applicant_name=student.full_name,
            email=student.email, registration_id=student.registration_id or '',
        )


class ApplicationDetailSerializer(serializers.ModelSerializer):
    cycle = CycleSerializer(read_only=True)
    department = serializers.CharField(source='student.department.name', default=None, read_only=True)
    age = serializers.IntegerField(read_only=True)
    is_editable = serializers.BooleanField(read_only=True)
    summary = serializers.SerializerMethodField()
    completion = serializers.SerializerMethodField()

    class Meta:
        model = m.Application
        exclude = ['student', 'reviewed_by']

    def get_fields(self):
        fields = super().get_fields()
        for name, (serializer_class, _, _) in NESTED.items():
            fields[name] = serializer_class(many=True, read_only=True)
        return fields

    def get_summary(self, obj):
        return summarize(obj)

    def get_completion(self, obj):
        return completion(obj)


# ---------- documents ----------

class DocumentSerializer(serializers.ModelSerializer):
    """A stored file. Its download link goes through a permission-checked view; no public media URL."""

    download_url = serializers.SerializerMethodField()
    uploaded_by = serializers.CharField(source='uploaded_by.full_name', read_only=True)

    class Meta:
        model = m.ApplicationDocument
        fields = ['id', 'slot', 'original_name', 'content_type', 'size', 'uploaded_by', 'uploaded_at',
                  'download_url']

    def get_download_url(self, obj):
        return f'/api/v1/scholarships/documents/{obj.pk}/download/'


class DocumentUploadSerializer(serializers.Serializer):
    slot = serializers.ChoiceField(choices=m.DocumentSlot.choices)
    file = serializers.FileField()


class DocumentReplaceSerializer(serializers.Serializer):
    file = serializers.FileField()


# ---------- Form 2 declarations ----------

class DeclarationSerializer(serializers.ModelSerializer):
    """One stamp-paper declaration: the printable text, its scan and whether the office has the original."""

    person = serializers.CharField(source='parent.get_role_display', read_only=True)
    person_name = serializers.CharField(source='parent.name', read_only=True)
    printable = serializers.SerializerMethodField()
    scan = serializers.SerializerMethodField()
    physical_received_by = serializers.CharField(source='physical_received_by.full_name', default=None,
                                                 read_only=True)
    can_upload_scan = serializers.SerializerMethodField()

    class Meta:
        model = m.Declaration
        fields = ['id', 'person', 'person_name', 'template', 'printable', 'scan', 'can_upload_scan',
                  'physical_received_on', 'physical_received_by', 'is_complete']

    def get_printable(self, obj):
        return render(obj)

    def get_scan(self, obj):
        if not obj.scan:
            return None
        return {'original_name': obj.scan_original_name, 'content_type': obj.scan_content_type,
                'size': obj.scan_size, 'uploaded_at': obj.scan_uploaded_at,
                'download_url': f'/api/v1/scholarships/declarations/{obj.pk}/scan/'}

    def get_can_upload_scan(self, obj):
        return scan_upload_allowed(obj)


def scan_upload_allowed(declaration):
    """Form 2 stays open after submission; a scan can no longer be replaced once the original is received."""
    if declaration.application.status in (ApplicationStatus.APPROVED, ApplicationStatus.REJECTED):
        return False
    return not (declaration.scan and declaration.physical_received_on)


class ReceiveSerializer(serializers.Serializer):
    received_on = serializers.DateField(required=False)

    def validate_received_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('The date cannot be in the future.')
        return value
