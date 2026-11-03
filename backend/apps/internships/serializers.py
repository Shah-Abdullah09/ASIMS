import re

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import Role

from .models import InternshipRequest, InternshipStatusChange
from .workflow import available_actions

PHONE_RE = re.compile(r'^\+?\d{10,13}$')
MIN_RELEVANCE = 50
MIN_WEEKS, MAX_WEEKS = 4, 26
REQUIRED = ['organisation', 'organisation_address', 'city', 'contact_name', 'contact_designation', 'contact_email',
            'contact_phone', 'field', 'role_title', 'start_date', 'end_date', 'mode', 'relevance']
EDITABLE = REQUIRED


class StudentRequestSerializer(serializers.ModelSerializer):
    """What the student fills in. Formats are checked on every save; completeness when submitting."""

    class Meta:
        model = InternshipRequest
        fields = EDITABLE

    def validate_contact_phone(self, value):
        value = value.replace(' ', '').replace('-', '')
        if value and not PHONE_RE.match(value):
            raise serializers.ValidationError('Enter a phone number of 10 to 13 digits, e.g. 03001234567.')
        return value

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'The end date must be after the start date.'})
        return attrs


def readiness(req):
    """What still stops the request from being submitted: {field: [message]}."""
    errors = {f: ['This field is required.'] for f in REQUIRED if getattr(req, f) in (None, '')}
    if req.start_date and req.end_date:
        weeks = req.weeks
        if not MIN_WEEKS <= weeks <= MAX_WEEKS:
            errors['end_date'] = [f'An internship lasts {MIN_WEEKS} to {MAX_WEEKS} weeks (this one is {weeks}).']
        if req.start_date < timezone.localdate():
            errors['start_date'] = ['The start date cannot be in the past.']
    if req.relevance and len(req.relevance.strip()) < MIN_RELEVANCE:
        errors['relevance'] = [f'Explain the relevance to your degree in at least {MIN_RELEVANCE} characters.']
    return {'ready': not errors, 'errors': errors}


class HistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.CharField(source='changed_by.full_name', read_only=True)
    changed_by_role = serializers.SerializerMethodField()
    to_label = serializers.CharField(source='get_to_status_display', read_only=True)

    class Meta:
        model = InternshipStatusChange
        fields = ['from_status', 'to_status', 'to_label', 'action', 'remarks', 'changed_by', 'changed_by_role',
                  'changed_at']

    def get_changed_by_role(self, obj) -> str:
        return Role(obj.role).label if obj.role in Role.values else obj.role


class RequestDetailSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    mode_label = serializers.CharField(source='get_mode_display', read_only=True)
    student = serializers.SerializerMethodField()
    weeks = serializers.IntegerField(read_only=True)
    is_editable = serializers.BooleanField(read_only=True)
    offer_letter = serializers.SerializerMethodField()
    letter = serializers.SerializerMethodField()
    faculty_supervisor = serializers.CharField(source='faculty_supervisor.full_name', default=None, read_only=True)
    faculty_supervisor_id = serializers.IntegerField(read_only=True)
    status_history = HistorySerializer(many=True, read_only=True)
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = InternshipRequest
        fields = ['id', 'status', 'status_label', 'student', 'submitted_at', 'created_at', 'updated_at', *EDITABLE,
                  'mode_label', 'weeks', 'is_editable', 'offer_letter', 'field_relevant', 'faculty_supervisor',
                  'faculty_supervisor_id', 'addressee_name', 'addressee_designation', 'extra_paragraph', 'letter',
                  'status_history', 'available_actions']

    def get_student(self, obj) -> dict:
        s = obj.student
        return {'id': s.pk, 'full_name': s.full_name, 'email': s.email, 'registration_id': s.registration_id,
                'department': s.department.name if s.department else None}

    def get_offer_letter(self, obj) -> dict | None:
        if not obj.offer_letter:
            return None
        return {'name': obj.offer_letter_name, 'size': obj.offer_letter_size,
                'download_url': f'/api/v1/internships/files/{obj.pk}/offer-letter/'}

    def get_letter(self, obj) -> dict | None:
        if not obj.letter_pdf:
            return None
        return {'reference': obj.letter_reference, 'issued_on': obj.issued_on,
                'download_url': f'/api/v1/internships/files/{obj.pk}/letter/'}

    def get_available_actions(self, obj) -> list:
        request = self.context.get('request')
        return available_actions(request.user, obj) if request else []


class ActionSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=30)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=2000, default='')
