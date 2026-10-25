"""Scholarship cycles and the AU Need Based Financial Grant application (Form 1),
with its supporting documents and stamp-paper income declarations (Form 2).

Fields are optional at the database level so a student can save a draft at any point;
the "required" rules are enforced when the application is submitted."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.documents.paths import declaration_scan_path, scholarship_document_path

from .choices import (PROFESSION_TEMPLATE, AccommodationStatus, AccommodationType, ApplicationStatus,
                      DeclarationTemplate,
                      AssetIncomeSource, AssetTitle, Division, DocumentSlot, EducationLevel, Gender,
                      LandCategory, LifeStatus, MaritalStatus, ParentRole, Profession, Relationship,
                      RentPaidBy, RoomRange, TransportType)
from .validators import cnic_validator, landline_validator, mobile_validator, ntn_validator


def money(**kwargs):
    """Whole Pakistani rupees, never negative."""
    return models.PositiveBigIntegerField(null=True, blank=True, **kwargs)


def cell():
    """One cell of a money grid; empty cells count as zero."""
    return models.PositiveBigIntegerField(default=0)


class ScholarshipCycle(models.Model):
    name = models.CharField(max_length=60, unique=True, help_text='e.g. Fall-26')
    opens_on = models.DateField()
    closes_on = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-opens_on']

    def __str__(self):
        return self.name

    def clean(self):
        if self.opens_on and self.closes_on and self.closes_on < self.opens_on:
            raise ValidationError({'closes_on': 'The closing date must be on or after the opening date.'})

    def is_open(self, today=None):
        today = today or timezone.localdate()
        return self.is_active and self.opens_on <= today <= self.closes_on


class Application(models.Model):
    cycle = models.ForeignKey(ScholarshipCycle, on_delete=models.PROTECT, related_name='applications')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name='scholarship_applications')
    status = models.CharField('stage', max_length=30, choices=ApplicationStatus.choices,
                              default=ApplicationStatus.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Latest staff action in the approval chain (the full record is in status_history)
    review_remarks = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                    related_name='reviewed_scholarship_applications')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    # Share of the semester tuition fee: recommended by the DAC, may be changed by Director, Registrar or VC
    scholarship_percentage = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(100)])

    # A. Applicant (Q1-8). Name, email and registration ID are copied from the profile.
    registration_id = models.CharField(max_length=8, blank=True)
    program = models.CharField('degree title / program', max_length=100, blank=True)
    applicant_name = models.CharField(max_length=150, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    marital_status = models.CharField(max_length=10, choices=MaritalStatus.choices, blank=True)
    cnic = models.CharField('applicant CNIC', max_length=15, blank=True, validators=[cnic_validator])
    date_of_birth = models.DateField(null=True, blank=True)
    domicile = models.CharField(max_length=60, blank=True)
    present_address = models.CharField(max_length=300, blank=True)
    permanent_address = models.CharField(max_length=300, blank=True)
    tel_residence = models.CharField(max_length=11, blank=True, validators=[landline_validator])
    mobile = models.CharField(max_length=13, blank=True, validators=[mobile_validator])
    email = models.EmailField(blank=True)

    # B. Household (Q9)
    total_family_members = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(30)])

    # Applicant's own earnings (Q25 rows 5-6)
    applicant_gross_income = money()
    applicant_net_income = money()

    # G. "Other (specify)" row of the asset income grid (Q24)
    asset_income_other_specify = models.CharField(max_length=120, blank=True)

    # I. Accommodation (Q26A)
    accommodation_type = models.CharField(max_length=20, choices=AccommodationType.choices, blank=True)
    accommodation_status = models.CharField(max_length=20, choices=AccommodationStatus.choices, blank=True)
    rent_paid_by = models.CharField(max_length=20, choices=RentPaidBy.choices, blank=True)
    plot_size_sqft = models.PositiveIntegerField(null=True, blank=True)
    covered_area_sqft = models.PositiveIntegerField(null=True, blank=True)
    accommodation_address = models.CharField(max_length=300, blank=True)
    bedrooms = models.CharField(max_length=10, choices=RoomRange.choices, blank=True)
    air_conditioners = models.CharField(max_length=10, choices=RoomRange.choices, blank=True)
    monthly_rent = money()
    other_house_owned = models.BooleanField(null=True, blank=True)
    other_house_details = models.CharField(max_length=300, blank=True)

    # J/K. Medical and miscellaneous expenditure (Q28-29)
    medical_monthly = money()
    misc_monthly = money()
    negative_income_explanation = models.TextField(blank=True)

    # L. Assets (Q32-34)
    owns_transport = models.BooleanField(null=True, blank=True)
    cattle_count = models.PositiveIntegerField(null=True, blank=True)
    cattle_kind = models.CharField(max_length=100, blank=True)

    # M. Financing (Q36-38)
    education_loan = models.BooleanField(null=True, blank=True)
    education_loan_details = models.TextField(blank=True)
    other_financing = models.TextField(blank=True)
    admission_fee_paid_how = models.TextField(blank=True)

    # N. Education and purpose (Q39 onward)
    last_institution_monthly_fee = money()
    other_scholarships = models.BooleanField(null=True, blank=True)
    statement_of_purpose = models.TextField(blank=True)

    # Page 6 undertaking: accepted online with the applicant's typed name (no e-signature)
    undertaking_accepted = models.BooleanField(default=False)
    undertaking_name = models.CharField(max_length=150, blank=True)
    undertaking_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['cycle', 'student'], name='one_application_per_student_per_cycle'),
            models.UniqueConstraint(fields=['cycle', 'cnic'], condition=~Q(cnic=''),
                                    name='unique_applicant_cnic_per_cycle'),
        ]

    def __str__(self):
        return f'#{self.pk} {self.applicant_name or self.student.email} ({self.cycle})'

    @property
    def is_editable(self):
        return self.status == ApplicationStatus.DRAFT

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class HouseholdMember(models.Model):
    """Q9: family members currently living with the applicant."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='household_members')
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=20, choices=Relationship.choices)
    marital_status = models.CharField(max_length=10, choices=MaritalStatus.choices, blank=True)
    remarks = models.CharField(max_length=200, blank=True)


class EarningMember(models.Model):
    """Q10 (and the net pay column of Q25)."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='earning_members')
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=20, choices=Relationship.choices)
    occupation = models.CharField(max_length=100, blank=True)
    organization = models.CharField(max_length=150, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    gross_pay = models.PositiveBigIntegerField()
    net_pay = models.PositiveBigIntegerField(null=True, blank=True)
    remarks = models.CharField(max_length=200, blank=True)

    def clean(self):
        if self.net_pay is not None and self.gross_pay is not None and self.net_pay > self.gross_pay:
            raise ValidationError({'net_pay': 'Net pay cannot be more than gross pay.'})


class StudyingMember(models.Model):
    """Q11: brothers, sisters, children or other family members studying."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='studying_members')
    name = models.CharField(max_length=150)
    relation = models.CharField(max_length=20, choices=Relationship.choices)
    institute = models.CharField('name and address of institute', max_length=300)
    fee_per_month = models.PositiveBigIntegerField()


class ParentGuardian(models.Model):
    """Q12-23 (father, mother) plus the optional guardian section."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='parents')
    role = models.CharField(max_length=10, choices=ParentRole.choices)
    name = models.CharField(max_length=150, blank=True)
    relationship_to_applicant = models.CharField(max_length=60, blank=True, help_text='Guardian only')
    cnic = models.CharField(max_length=15, blank=True, validators=[cnic_validator])
    status = models.CharField(max_length=10, choices=LifeStatus.choices, default=LifeStatus.ALIVE)
    profession = models.CharField(max_length=20, choices=Profession.choices, blank=True)
    employer = models.CharField('name of company / employer', max_length=150, blank=True)
    tel_office = models.CharField(max_length=11, blank=True, validators=[landline_validator])
    mobile = models.CharField(max_length=13, blank=True, validators=[mobile_validator])
    occupation_type = models.CharField(max_length=100, blank=True)
    ntn = models.CharField('NTN', max_length=13, blank=True, validators=[ntn_validator])
    designation_grade = models.CharField('designation & grade', max_length=100, blank=True)
    gross_monthly_income = money()
    net_monthly_income = money()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['application', 'role'], name='one_parent_per_role')]

    def __str__(self):
        return f'{self.get_role_display()}: {self.name}'

    def clean(self):
        if (self.net_monthly_income is not None and self.gross_monthly_income is not None
                and self.net_monthly_income > self.gross_monthly_income):
            raise ValidationError({'net_monthly_income': 'Net income cannot be more than gross income.'})

    @property
    def declaration_template(self):
        """The Form 2 template this person signs, or None if they need not declare income."""
        if self.status != LifeStatus.ALIVE:
            return None
        return PROFESSION_TEMPLATE.get(self.profession)


class AssetIncome(models.Model):
    """Q24: one row per income source, one column per holder."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='asset_income')
    source = models.CharField(max_length=20, choices=AssetIncomeSource.choices)
    father = cell()
    mother = cell()
    spouse = cell()
    self_amount = cell()
    other = cell()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['application', 'source'], name='one_asset_income_row_per_source')]

    @property
    def total(self):
        return self.father + self.mother + self.spouse + self.self_amount + self.other


class UtilityMonth(models.Model):
    """Q27: last three months of utility bills paid."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='utility_months')
    month_index = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    telephone = cell()
    electricity = cell()
    gas = cell()
    water = cell()

    class Meta:
        ordering = ['month_index']
        constraints = [models.UniqueConstraint(fields=['application', 'month_index'], name='one_utility_row_per_month')]

    @property
    def total(self):
        return self.telephone + self.electricity + self.gas + self.water


class Vehicle(models.Model):
    """Q32: transport owned by the family."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='vehicles')
    transport_type = models.CharField(max_length=20, choices=TransportType.choices)
    transport_type_other = models.CharField(max_length=60, blank=True)
    make_model = models.CharField(max_length=100)
    engine_cc = models.PositiveIntegerField(validators=[MinValueValidator(50), MaxValueValidator(10000)])
    registration_no = models.CharField(max_length=20)
    ownership_period = models.CharField(max_length=40)


class LandHolding(models.Model):
    """Q34: land and plots owned, one row per category."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='land_holdings')
    category = models.CharField(max_length=20, choices=LandCategory.choices)
    quantity = models.PositiveIntegerField(default=0)
    size = models.CharField(max_length=60, blank=True)
    location = models.CharField(max_length=300, blank=True)
    cultivable_area = models.CharField(max_length=60, blank=True, help_text='Agricultural land only')
    yield_per_acre = models.CharField(max_length=60, blank=True, help_text='Agricultural land only')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['application', 'category'], name='one_land_row_per_category')]


class AssetWorth(models.Model):
    """Q35: current market value of assets, one row per asset title."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='asset_worth')
    title = models.CharField(max_length=20, choices=AssetTitle.choices)
    father = cell()
    mother = cell()
    spouse = cell()
    self_amount = cell()
    guardian = cell()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['application', 'title'], name='one_asset_worth_row_per_title')]

    @property
    def total(self):
        return self.father + self.mother + self.spouse + self.self_amount + self.guardian


class EducationRecord(models.Model):
    """Q39: Bachelors, Intermediate and Secondary."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='education_records')
    level = models.CharField(max_length=20, choices=EducationLevel.choices)
    institute = models.CharField('name and location of institute', max_length=300)
    monthly_fee = models.PositiveBigIntegerField(null=True, blank=True)
    from_month = models.DateField(help_text='First day of the starting month')
    to_month = models.DateField(help_text='First day of the finishing month')
    division = models.CharField(max_length=5, choices=Division.choices, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                     validators=[MinValueValidator(0), MaxValueValidator(100)])
    cgpa = models.DecimalField('CGPA', max_digits=3, decimal_places=2, null=True, blank=True,
                               validators=[MinValueValidator(0), MaxValueValidator(4)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=['application', 'level'], name='one_education_row_per_level')]

    def clean(self):
        if self.from_month and self.to_month and self.to_month < self.from_month:
            raise ValidationError({'to_month': 'The finishing month must be on or after the starting month.'})
        if not self.division and self.percentage is None and self.cgpa is None:
            raise ValidationError('Enter a division, a percentage or a CGPA.')


class PreviousScholarship(models.Model):
    """Other scholarships the applicant has received."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='previous_scholarships')
    institute = models.CharField(max_length=150)
    scholarship_name = models.CharField(max_length=150)
    total_amount = models.PositiveBigIntegerField()
    period = models.CharField(max_length=60)
    level = models.CharField('class / level granted at', max_length=60)


class ApplicationDocument(models.Model):
    """A supporting document uploaded into one of the labelled checklist slots."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    slot = models.CharField(max_length=30, choices=DocumentSlot.choices)
    file = models.FileField(upload_to=scholarship_document_path, max_length=255)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField(help_text='Bytes')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name='uploaded_scholarship_documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['slot', 'uploaded_at']

    def __str__(self):
        return f'{self.get_slot_display()} - {self.original_name}'


class Declaration(models.Model):
    """Form 2: a stamp-paper income declaration, one per earning parent or guardian.
    The scan is uploaded online; the original is handed to the office."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='declarations')
    parent = models.OneToOneField(ParentGuardian, on_delete=models.CASCADE, related_name='declaration')
    # Template the text was produced from; a later profession change makes an existing scan invalid
    template = models.CharField(max_length=20, choices=DeclarationTemplate.choices)
    scan = models.FileField(upload_to=declaration_scan_path, max_length=255, blank=True)
    scan_original_name = models.CharField(max_length=255, blank=True)
    scan_content_type = models.CharField(max_length=50, blank=True)
    scan_size = models.PositiveIntegerField(null=True, blank=True)
    scan_uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                         related_name='uploaded_declaration_scans')
    scan_uploaded_at = models.DateTimeField(null=True, blank=True)
    physical_received_on = models.DateField(null=True, blank=True)
    physical_received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                             on_delete=models.PROTECT, related_name='received_declarations')

    def __str__(self):
        return f'Declaration of {self.parent}'

    @property
    def is_complete(self):
        return bool(self.scan) and self.physical_received_on is not None


class StatusChange(models.Model):
    """Every move along the approval chain: who took which action, from which stage to which, and why."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=30, choices=ApplicationStatus.choices)
    to_status = models.CharField(max_length=30, choices=ApplicationStatus.choices)
    action = models.CharField(max_length=30, blank=True, help_text='Workflow action, e.g. verify or approve')
    remarks = models.TextField(blank=True)
    percentage = models.PositiveSmallIntegerField(null=True, blank=True,
                                                  help_text='Scholarship % recommended or approved by this action')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='scholarship_status_changes')
    role = models.CharField(max_length=30, blank=True, help_text='Role of the person at the time of the action')
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['changed_at', 'pk']

    def __str__(self):
        return f'#{self.application_id}: {self.from_status} -> {self.to_status}'
