"""The internship request chain:

Draft -> Submitted to DIC -> Pending Placement approval -> Approved, letter issued. The DIC forwards the request or
returns it to the student; the Placement Office approves, returns or rejects it. A returned request is corrected
and submitted to the DIC again. A rejection ends it.

The Administrator sees every stage but takes only the Placement Office actions."""
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import PLACEMENT_ROLES as PLACEMENT, Role
from apps.workflow.chain import Chain
from apps.workflow.engine import Transition, Workflow

from .choices import InternshipStatus as S
from .models import Internship, InternshipStatusChange

REQUIRED = {'program': 'Choose your program.', 'semester': 'Enter your semester.',
            'company': 'Choose the company.', 'start_date': 'Enter the starting date.',
            'duration_weeks': 'Enter the expected duration.', 'mode': 'Choose on-site, remote or hybrid.'}


def own_request(user, internship):
    return internship.student_id == user.pk


def own_department(user, internship):
    return user.department_id is not None and user.department_id == internship.student.department_id


TRANSITIONS = [
    Transition('submit', 'Submit to DIC', S.DRAFT, S.DIC_REVIEW, (Role.STUDENT,), scope=own_request),
    Transition('resubmit', 'Submit to DIC again', S.RETURNED, S.DIC_REVIEW, (Role.STUDENT,), scope=own_request),
    Transition('forward', 'Forward to Placement Office', S.DIC_REVIEW, S.PLACEMENT_APPROVAL, (Role.DIC,),
               scope=own_department),
    Transition('return', 'Return to student', S.DIC_REVIEW, S.RETURNED, (Role.DIC,), remarks_required=True,
               scope=own_department),
    Transition('approve', 'Approve', S.PLACEMENT_APPROVAL, S.APPROVED, PLACEMENT),
    Transition('return', 'Return to student', S.PLACEMENT_APPROVAL, S.RETURNED, PLACEMENT, remarks_required=True),
    Transition('reject', 'Reject', S.PLACEMENT_APPROVAL, S.REJECTED, PLACEMENT, remarks_required=True),
]

CHAIN = Workflow(TRANSITIONS, S.choices)


def check_complete(internship):
    """Every field of the request must be filled in before it goes to the DIC."""
    missing = {field: message for field, message in REQUIRED.items() if getattr(internship, field) in (None, '')}
    if missing:
        raise ValidationError(missing)


CHECKS = {('submit', S.DRAFT): check_complete, ('resubmit', S.RETURNED): check_complete}


def update_internship(internship, transition, user, remarks, values):
    if transition.action == 'submit':
        internship.submitted_at = timezone.now()
        return ['submitted_at']
    return []


RUNNER = Chain(CHAIN, Internship, InternshipStatusChange, 'internship', related=('student__department',),
               checks=CHECKS, update=update_internship)
