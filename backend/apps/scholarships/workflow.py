"""The scholarship approval chain:

Draft -> Placement verification -> DAC review -> Awaiting forwarding -> Director review -> Registrar review
-> VC review -> Awaiting fee adjustment -> Completed (Finance records the fee adjustment). Placement may return
a case to the student, who resubmits it. A rejection at any stage ends the case.

The Administrator sees every stage but takes only the Placement Office actions."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role
from apps.audit.log import record
from apps.audit.models import AuditAction
from apps.workflow.chain import Chain
from apps.workflow.engine import Transition, Workflow

from .choices import ApplicationStatus as S
from .access import PLACEMENT
from .alerts import case_moved
from .emails import notify_student
from .letters import issue_award_letter
from .models import Application, StatusChange
from .verification import check_returnable, check_verifiable, resolve_flags


def own_application(user, app):
    return app.student_id == user.pk


def own_department(user, app):
    return user.department_id is not None and user.department_id == app.student.department_id


TRANSITIONS = [
    Transition('submit', 'Submit', S.DRAFT, S.PLACEMENT_VERIFICATION, (Role.STUDENT,), scope=own_application),
    Transition('resubmit', 'Resubmit', S.RETURNED, S.PLACEMENT_VERIFICATION, (Role.STUDENT,),
               scope=own_application),
    Transition('verify', 'Verify and send to DAC', S.PLACEMENT_VERIFICATION, S.DAC_REVIEW, PLACEMENT),
    Transition('return', 'Return to student', S.PLACEMENT_VERIFICATION, S.RETURNED, PLACEMENT,
               remarks_required=True),
    Transition('reject', 'Reject', S.PLACEMENT_VERIFICATION, S.REJECTED, PLACEMENT, remarks_required=True),
    Transition('shortlist', 'Shortlist', S.DAC_REVIEW, S.AWAITING_FORWARDING, (Role.DAC_MEMBER,),
               scope=own_department),
    Transition('not_shortlisted', 'Not shortlisted', S.DAC_REVIEW, S.REJECTED, (Role.DAC_MEMBER,),
               remarks_required=True, scope=own_department),
    Transition('forward', 'Forward to Director', S.AWAITING_FORWARDING, S.DIRECTOR_REVIEW, PLACEMENT),
    Transition('approve', 'Approve', S.DIRECTOR_REVIEW, S.REGISTRAR_REVIEW, (Role.DIRECTOR,)),
    Transition('reject', 'Reject', S.DIRECTOR_REVIEW, S.REJECTED, (Role.DIRECTOR,), remarks_required=True),
    Transition('approve', 'Approve', S.REGISTRAR_REVIEW, S.VC_REVIEW, (Role.REGISTRAR,)),
    Transition('reject', 'Reject', S.REGISTRAR_REVIEW, S.REJECTED, (Role.REGISTRAR,), remarks_required=True),
    Transition('approve', 'Approve', S.VC_REVIEW, S.AWAITING_FEE_ADJUSTMENT, (Role.VICE_CHANCELLOR,)),
    Transition('reject', 'Reject', S.VC_REVIEW, S.REJECTED, (Role.VICE_CHANCELLOR,), remarks_required=True),
    Transition('record_fee_adjustment', 'Record fee adjustment', S.AWAITING_FEE_ADJUSTMENT, S.COMPLETED,
               (Role.FINANCE_OFFICER,)),
]

CHAIN = Workflow(TRANSITIONS, S.choices)

# Actions that carry a scholarship percentage: the DAC must give one, approvers may change it
PERCENTAGE = {'shortlist': 'required', 'approve': 'optional'}

STUDENT_ACTIONS = {'submit', 'resubmit'}


# Extra conditions of a transition, keyed by (action, source stage). Each raises ValidationError.
def check_interviewed(app):
    if app.interview_date is None:
        raise ValidationError({'action': 'Record the interview date and remarks before shortlisting.'})


def check_fee_adjustment(app):
    if not hasattr(app, 'fee_adjustment'):
        raise ValidationError({'action': 'Enter the fee adjustment details first.'})


CHECKS = {
    ('record_fee_adjustment', S.AWAITING_FEE_ADJUSTMENT): check_fee_adjustment,
    ('shortlist', S.DAC_REVIEW): check_interviewed,
    ('verify', S.PLACEMENT_VERIFICATION): check_verifiable,
    ('return', S.PLACEMENT_VERIFICATION): check_returnable,
}

# Follow-up work done in the same transaction after a transition, keyed the same way: (app, user)
def after_vc_approval(app, user):
    """The award letter is generated as soon as the Vice Chancellor approves."""
    letter = issue_award_letter(app)
    record(AuditAction.AWARD_LETTER_GENERATED, actor=user, target=letter, application=app.pk,
           reference=letter.reference, percentage=letter.percentage)


AFTER = {
    ('resubmit', S.RETURNED): resolve_flags,
    ('approve', S.VC_REVIEW): after_vc_approval,
}


def action_info(transition):
    """What a screen needs to offer the action."""
    return {'action': transition.action, 'label': transition.label, 'to_status': transition.target,
            'remarks_required': transition.remarks_required, 'percentage': PERCENTAGE.get(transition.action)}


def available_actions(user, app):
    return [action_info(t) for t in CHAIN.available(user, app, app.status)]


def clean_percentage(transition, percentage=None):
    rule = PERCENTAGE.get(transition.action)
    if percentage in (None, ''):
        if rule == 'required':
            raise ValidationError({'percentage': 'Give the recommended scholarship percentage (1-100).'})
        return {'percentage': None}
    if rule is None:
        raise ValidationError({'percentage': f'"{transition.label}" does not take a percentage.'})
    if isinstance(percentage, bool) or not isinstance(percentage, int) or not 1 <= percentage <= 100:
        raise ValidationError({'percentage': 'Enter a whole number from 1 to 100.'})
    return {'percentage': percentage}


def update_application(app, transition, user, remarks, values):
    """The application's own fields set by an action: submission time, last review and the percentage."""
    now = timezone.now()
    fields = []
    if transition.action == 'submit':
        app.submitted_at = now
        fields.append('submitted_at')
    if transition.action not in STUDENT_ACTIONS:
        app.review_remarks, app.reviewed_by, app.reviewed_at = remarks, user, now
        fields += ['review_remarks', 'reviewed_by', 'reviewed_at']
    if values['percentage'] is not None:
        app.scholarship_percentage = values['percentage']
        fields.append('scholarship_percentage')
    return fields


def tell_people(app, change, user):
    transaction.on_commit(lambda: notify_student(app, change))
    case_moved(app, change, user)


RUNNER = Chain(CHAIN, Application, StatusChange, 'application', related=('student__department', 'cycle'),
               clean=clean_percentage, checks=CHECKS, update=update_application, after=AFTER,
               on_moved=tell_people)
perform = RUNNER.perform
