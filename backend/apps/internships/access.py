"""Which internship requests each person can open (list, page and files)."""
from apps.accounts.models import Role

from .models import InternshipRequest, InternshipStatus

PLACEMENT = (Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR)
STAFF_ROLES = (*PLACEMENT, Role.DIC, Role.FACULTY_SUPERVISOR)


def visible_requests(user):
    """Submitted requests (never drafts): Placement and Administrator see all; a DIC sees their department's;
    a Faculty Supervisor sees the requests assigned to them."""
    requests = InternshipRequest.objects.exclude(status=InternshipStatus.DRAFT)
    if user.role in PLACEMENT:
        return requests
    if user.role == Role.DIC and user.department_id:
        return requests.filter(student__department_id=user.department_id)
    if user.role == Role.FACULTY_SUPERVISOR:
        return requests.filter(faculty_supervisor=user)
    return requests.none()


def can_open(user, req):
    return req.student_id == user.pk or visible_requests(user).filter(pk=req.pk).exists()
