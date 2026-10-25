"""Which submitted applications each staff role can see. One rule for the case list, the case page and
file downloads, so a role never reaches a file of a case it cannot open."""
from apps.accounts.models import Role

from .choices import ApplicationStatus
from .models import Application

PLACEMENT = (Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR)
STAFF_ROLES = (*PLACEMENT, Role.DAC_MEMBER)


def visible_cases(user):
    """Submitted applications this user may open (drafts are never shown to staff).

    Placement Office and Administrator: every stage. DAC member: cases of their own department while
    they are at DAC review."""
    cases = Application.objects.exclude(status=ApplicationStatus.DRAFT)
    if user.role in PLACEMENT:
        return cases
    if user.role == Role.DAC_MEMBER and user.department_id:
        return cases.filter(status=ApplicationStatus.DAC_REVIEW, student__department_id=user.department_id)
    return cases.none()


def can_open(user, app):
    """The owner, or staff who can see the case."""
    return app.student_id == user.pk or visible_cases(user).filter(pk=app.pk).exists()
