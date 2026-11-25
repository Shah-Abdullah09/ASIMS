from django.db import models


class InternshipStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    DIC_REVIEW = 'dic_review', 'Submitted to DIC'
    RETURNED = 'returned', 'Returned to student'
    PLACEMENT_APPROVAL = 'placement_approval', 'Pending Placement approval'
    APPROVED = 'approved', 'Approved, letter issued'
    REJECTED = 'rejected', 'Rejected'


class InternshipMode(models.TextChoices):
    ON_SITE = 'on_site', 'On-site'
    REMOTE = 'remote', 'Remote'
    HYBRID = 'hybrid', 'Hybrid'


# Internship policy: duration in weeks (6 weeks to 6 months)
MIN_WEEKS, MAX_WEEKS = 6, 26
