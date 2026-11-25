"""Internship requests and the shared list of companies.

Fields are optional at the database level so a student can save a draft; they are required when the request is
submitted (see workflow.check_complete)."""
from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.models import Program
from apps.workflow.models import StatusChangeBase

from .choices import MAX_WEEKS, MIN_WEEKS, InternshipMode, InternshipStatus


class Company(models.Model):
    """An organisation that takes interns. One shared list: students choose a company or add a new one, and the
    Placement Office corrects the details."""
    name = models.CharField(max_length=200)
    address = models.TextField()
    contact_person = models.CharField(max_length=150, blank=True, help_text='Addressee of the recommendation letter')
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='added_companies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'companies'
        constraints = [models.UniqueConstraint(Lower('name'), name='unique_company_name')]

    def __str__(self):
        return self.name


class Internship(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='internships')
    status = models.CharField('stage', max_length=30, choices=InternshipStatus.choices,
                              default=InternshipStatus.DRAFT)
    program = models.ForeignKey(Program, null=True, blank=True, on_delete=models.PROTECT, related_name='internships')
    semester = models.PositiveSmallIntegerField(null=True, blank=True,
                                                validators=[MinValueValidator(1), MaxValueValidator(12)])
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.PROTECT, related_name='internships')
    start_date = models.DateField(null=True, blank=True)
    duration_weeks = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(MIN_WEEKS), MaxValueValidator(MAX_WEEKS)])
    mode = models.CharField(max_length=10, choices=InternshipMode.choices, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        # A student may have several internships over the degree, but only one open at a time
        constraints = [models.UniqueConstraint(fields=['student'], condition=~Q(status=InternshipStatus.REJECTED),
                                               name='one_open_internship_per_student')]

    def __str__(self):
        return self.reference

    @property
    def reference(self):
        """The Internship ID shown to everyone, e.g. INT-2026-0007."""
        return f'INT-{timezone.localtime(self.created_at):%Y}-{self.pk:04d}'

    @property
    def end_date(self):
        if self.start_date and self.duration_weeks:
            return self.start_date + timedelta(weeks=self.duration_weeks)
        return None


class InternshipStatusChange(StatusChangeBase):
    """Every move along the internship chain."""
    internship = models.ForeignKey(Internship, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=30, choices=InternshipStatus.choices)
    to_status = models.CharField(max_length=30, choices=InternshipStatus.choices)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='internship_status_changes')

    def __str__(self):
        return f'#{self.internship_id}: {self.from_status} -> {self.to_status}'
