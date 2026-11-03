"""Internship requests: the student asks for an internship letter, the DIC checks the field is relevant and
assigns a Faculty Supervisor, the Placement Office prepares the letter, the supervisor reviews it, the DIC
confirms it and the Placement Office issues the final PDF."""
from django.conf import settings
from django.db import models

from apps.documents.paths import system_file_name


def internship_file_path(instance, filename):
    return f'internships/{instance.student_id}/{instance.pk or "new"}/{system_file_name(filename)}'


class InternshipStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    DIC_REVIEW = 'dic_review', 'DIC review'
    RETURNED = 'returned', 'Returned to student'
    LETTER_PREPARATION = 'letter_preparation', 'Letter preparation'
    SUPERVISOR_REVIEW = 'supervisor_review', 'Supervisor review'
    DIC_CONFIRMATION = 'dic_confirmation', 'DIC confirmation'
    READY_TO_ISSUE = 'ready_to_issue', 'Ready to issue'
    ISSUED = 'issued', 'Issued'
    REJECTED = 'rejected', 'Rejected'
    WITHDRAWN = 'withdrawn', 'Withdrawn'


CLOSED = (InternshipStatus.ISSUED, InternshipStatus.REJECTED, InternshipStatus.WITHDRAWN)


class Mode(models.TextChoices):
    ONSITE = 'onsite', 'On-site'
    REMOTE = 'remote', 'Remote'
    HYBRID = 'hybrid', 'Hybrid'


class InternshipRequest(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='internship_requests')
    status = models.CharField('stage', max_length=30, choices=InternshipStatus.choices, default=InternshipStatus.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # The organisation
    organisation = models.CharField(max_length=200, blank=True)
    organisation_address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=80, blank=True)
    contact_name = models.CharField('contact person', max_length=150, blank=True)
    contact_designation = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=13, blank=True)

    # The internship
    field = models.CharField('field / area', max_length=150, blank=True)
    role_title = models.CharField('role or title', max_length=150, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    mode = models.CharField(max_length=10, choices=Mode.choices, blank=True)
    relevance = models.TextField('relevance to the degree', blank=True)

    # Optional offer letter or organisation email
    offer_letter = models.FileField(upload_to=internship_file_path, max_length=255, blank=True)
    offer_letter_name = models.CharField(max_length=255, blank=True)
    offer_letter_type = models.CharField(max_length=50, blank=True)
    offer_letter_size = models.PositiveIntegerField(null=True, blank=True)

    # DIC approval
    field_relevant = models.BooleanField(null=True, blank=True)
    faculty_supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                           related_name='supervised_internships')

    # The letter (prepared by Placement, reviewed by the supervisor, confirmed by the DIC, issued by Placement)
    addressee_name = models.CharField(max_length=150, blank=True)
    addressee_designation = models.CharField(max_length=150, blank=True)
    extra_paragraph = models.TextField(blank=True)
    letter_reference = models.CharField(max_length=40, blank=True)
    letter_pdf = models.FileField(upload_to=internship_file_path, max_length=255, blank=True)
    issued_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'Internship #{self.pk} {self.student.email} at {self.organisation or "?"}'

    @property
    def weeks(self):
        if self.start_date and self.end_date:
            return ((self.end_date - self.start_date).days + 1 + 6) // 7
        return None

    @property
    def is_editable(self):
        return self.status in (InternshipStatus.DRAFT, InternshipStatus.RETURNED)


class InternshipStatusChange(models.Model):
    request = models.ForeignKey(InternshipRequest, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=30, choices=InternshipStatus.choices)
    to_status = models.CharField(max_length=30, choices=InternshipStatus.choices)
    action = models.CharField(max_length=30)
    remarks = models.TextField(blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='internship_status_changes')
    role = models.CharField(max_length=30, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['changed_at', 'pk']

