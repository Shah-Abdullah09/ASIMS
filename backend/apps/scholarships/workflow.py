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
from apps.workflow.engine import Transition, Workflow

from .choices import ApplicationStatus as S
from .access import PLACEMENT
from .emails import notify_student
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
AFTER = {
    ('resubmit', S.RETURNED): resolve_flags,
}


def action_info(transition):
    """What a screen needs to offer the action."""
    return {'action': transition.action, 'label': transition.label, 'to_status': transition.target,
            'remarks_required': transition.remarks_required, 'percentage': PERCENTAGE.get(transition.action)}


def available_actions(user, app):
    return [action_info(t) for t in CHAIN.available(user, app, app.status)]


def clean_percentage(transition, percentage):
    rule = PERCENTAGE.get(transition.action)
    if percentage in (None, ''):
        if rule == 'required':
            raise ValidationError({'percentage': 'Give the recommended scholarship percentage (1-100).'})
        return None
    if rule is None:
        raise ValidationError({'percentage': f'"{transition.label}" does not take a percentage.'})
    if isinstance(percentage, bool) or not isinstance(percentage, int) or not 1 <= percentage <= 100:
        raise ValidationError({'percentage': 'Enter a whole number from 1 to 100.'})
    return percentage


def perform(app_id, action, user, *, remarks='', percentage=None, request=None):
    """Take `action` on the application as `user` and record it. The row is locked first, so when two people
    act at once the second gets a WorkflowError ('stage_conflict') instead of moving the case twice."""
    with transaction.atomic():
        app = (Application.objects.select_for_update(of=('self',)).select_related('student', 'cycle')
               .get(pk=app_id))
        transition = CHAIN.find(user, app, app.status, action)
        remarks = (remarks or '').strip()
        if transition.remarks_required and not remarks:
            raise ValidationError({'remarks': 'Remarks are required for this action, so the reason is on record.'})
        percentage = clean_percentage(transition, percentage)
        if check := CHECKS.get((transition.action, transition.source)):
            check(app)

        now = timezone.now()
        change = StatusChange.objects.create(
            application=app, from_status=transition.source, to_status=transition.target, action=transition.action,
            remarks=remarks, percentage=percentage, changed_by=user, role=user.role)
        fields = ['status', 'updated_at']
        app.status = transition.target
        if transition.action == 'submit':
            app.submitted_at = now
            fields.append('submitted_at')
        if transition.action not in STUDENT_ACTIONS:
            app.review_remarks, app.reviewed_by, app.reviewed_at = remarks, user, now
            fields += ['review_remarks', 'reviewed_by', 'reviewed_at']
        if percentage is not None:
            app.scholarship_percentage = percentage
            fields.append('scholarship_percentage')
        app.save(update_fields=fields)
        if after := AFTER.get((transition.action, transition.source)):
            after(app, user)
        transaction.on_commit(lambda: notify_student(app, change))
        record(AuditAction.WORKFLOW_ACTION, request=request, actor=user, target=app, action=transition.action,
               from_status=transition.source, to_status=transition.target, remarks=remarks, percentage=percentage)
    return app
