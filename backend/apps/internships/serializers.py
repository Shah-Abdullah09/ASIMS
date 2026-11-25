from rest_framework import serializers

from apps.workflow.serializers import StatusChangeSerializer

from .choices import InternshipStatus
from .models import Company, Internship, InternshipStatusChange


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'address', 'contact_person', 'contact_email', 'contact_phone']

    def validate_name(self, value):
        value = value.strip()
        same = Company.objects.filter(name__iexact=value)
        if self.instance:
            same = same.exclude(pk=self.instance.pk)
        if same.exists():
            raise serializers.ValidationError('This company is already in the list. Choose it instead of adding it '
                                              'again.')
        return value


class InternshipStatusChangeSerializer(StatusChangeSerializer):
    class Meta(StatusChangeSerializer.Meta):
        model = InternshipStatusChange


class InternshipSerializer(serializers.ModelSerializer):
    """A student's internship request: the fields they fill in, and where it stands."""
    reference = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    program_name = serializers.CharField(source='program.name', read_only=True, default=None)
    company_detail = CompanySerializer(source='company', read_only=True)
    end_date = serializers.DateField(read_only=True)
    status_history = InternshipStatusChangeSerializer(many=True, read_only=True)

    class Meta:
        model = Internship
        fields = ['id', 'reference', 'status', 'status_label', 'program', 'program_name', 'semester', 'company',
                  'company_detail', 'start_date', 'duration_weeks', 'end_date', 'mode', 'submitted_at',
                  'status_history']
        read_only_fields = ['status', 'submitted_at']

    def validate_program(self, program):
        student = self.context['request'].user
        if program is not None and (program.department_id != student.department_id or not program.is_active):
            raise serializers.ValidationError('Choose an active program of your department.')
        return program

    def validate(self, attrs):
        student = self.context['request'].user
        if self.instance is None and student.internships.exclude(status=InternshipStatus.REJECTED).exists():
            raise serializers.ValidationError('You already have an internship request. Only one can be open at a '
                                              'time.')
        return attrs

    def create(self, validated):
        student = self.context['request'].user
        validated.setdefault('program', student.program)  # prefilled from the student's profile
        return Internship.objects.create(student=student, **validated)


class SubmitSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=2000, default='')
