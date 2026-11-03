"""The internship chain, built on the same engine as the scholarship chain:

Draft -> DIC review -> Letter preparation -> Supervisor review -> DIC confirmation -> Ready to issue -> Issued.
The DIC may return a request to the student (who resubmits) or reject it; the supervisor and the DIC may send the
letter back to Placement. The student may withdraw until the DIC has approved. The Administrator takes the
Placement actions."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role, User
from apps.audit.log import record
from apps.audit.models import AuditAction
from apps.notifications.service import notify
from apps.workflow.engine import Transition, Workflow

from .models import InternshipRequest, InternshipStatus as S, InternshipStatusChange

PLACEMENT = (Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR)


def own_request(user, req):
    return req.student_id == user.pk


def department_dic(user, req):
    return user.department_id is not None and user.department_id == req.student.department_id


def assigned_supervisor(user, req):
    return req.faculty_supervisor_id == user.pk


DIC = (Role.DIC,)
TRANSITIONS = [
    Transition('submit', 'Submit', S.DRAFT, S.DIC_REVIEW, (Role.STUDENT,), scope=own_request),
    Transition('resubmit', 'Resubmit', S.RETURNED, S.DIC_REVIEW, (Role.STUDENT,), scope=own_request),
    *[Transition('withdraw', 'Withdraw', source, S.WITHDRAWN, (Role.STUDENT,), scope=own_request)
      for source in (S.DRAFT, S.DIC_REVIEW, S.RETURNED)],
    Transition('approve', 'Approve', S.DIC_REVIEW, S.LETTER_PREPARATION, DIC, scope=department_dic),
    Transition('return', 'Return to student', S.DIC_REVIEW, S.RETURNED, DIC, remarks_required=True,
               scope=department_dic),
    Transition('reject', 'Reject', S.DIC_REVIEW, S.REJECTED, DIC, remarks_required=True, scope=department_dic),
    Transition('send_for_review', 'Send to the supervisor', S.LETTER_PREPARATION, S.SUPERVISOR_REVIEW, PLACEMENT),
    Transition('approve_letter', 'Approve the letter', S.SUPERVISOR_REVIEW, S.DIC_CONFIRMATION,
               (Role.FACULTY_SUPERVISOR,), scope=assigned_supervisor),
    Transition('return_letter', 'Send back to Placement', S.SUPERVISOR_REVIEW, S.LETTER_PREPARATION,
               (Role.FACULTY_SUPERVISOR,), remarks_required=True, scope=assigned_supervisor),
    Transition('confirm', 'Confirm', S.DIC_CONFIRMATION, S.READY_TO_ISSUE, DIC, scope=department_dic),
    Transition('return_letter', 'Send back to Placement', S.DIC_CONFIRMATION, S.LETTER_PREPARATION, DIC,
               remarks_required=True, scope=department_dic),
    Transition('issue', 'Issue the letter', S.READY_TO_ISSUE, S.ISSUED, PLACEMENT),
]
CHAIN = Workflow(TRANSITIONS, S.choices)


def check_approval(req):
    if not req.field_relevant or req.faculty_supervisor_id is None:
        raise ValidationError({'action': 'Confirm the field is relevant and assign a Faculty Supervisor first.'})


def check_letter(req):
    if not req.addressee_name.strip() or not req.addressee_designation.strip():
        raise ValidationError({'action': "Enter the addressee's name and designation for the letter first."})


CHECKS = {('approve', S.DIC_REVIEW): check_approval, ('send_for_review', S.LETTER_PREPARATION): check_letter}
AFTER = {}  # filled by letters.py (the PDF is generated on issue)

STUDENT_PHRASE = {
    S.DIC_REVIEW: 'is with your Departmental Internship Coordinator',
    S.RETURNED: 'was returned to you for corrections',
    S.LETTER_PREPARATION: 'was approved; the Placement Office is preparing your letter',
    S.SUPERVISOR_REVIEW: 'is with your Faculty Supervisor for review',
    S.DIC_CONFIRMATION: 'is with your Departmental Internship Coordinator for confirmation',
    S.READY_TO_ISSUE: 'is ready; the Placement Office will issue your letter',
    S.ISSUED: 'is complete: your internship letter has been issued',
    S.REJECTED: 'was not approved',
    S.WITHDRAWN: 'was withdrawn',
}
STUDENT_EMAIL = {S.RETURNED, S.REJECTED, S.ISSUED}


def queue_recipients(req, stage):
    """Who has work to do when a request reaches `stage`."""
    if stage in (S.DIC_REVIEW, S.DIC_CONFIRMATION):
        return User.objects.filter(role=Role.DIC, is_active=True, department_id=req.student.department_id)
    if stage in (S.LETTER_PREPARATION, S.READY_TO_ISSUE):
        return User.objects.filter(role=Role.PLACEMENT_OFFICER, is_active=True)
    if stage == S.SUPERVISOR_REVIEW and req.faculty_supervisor_id:
        return User.objects.filter(pk=req.faculty_supervisor_id, is_active=True)
    return User.objects.none()


def available_actions(user, req):
    return [{'action': t.action, 'label': t.label, 'to_status': t.target, 'remarks_required': t.remarks_required}
            for t in CHAIN.available(user, req, req.status)]


def perform(req_id, action, user, *, remarks='', request=None):
    """Take `action` on the request as `user`, with the row locked so two people cannot both move it."""
    with transaction.atomic():
        req = (InternshipRequest.objects.select_for_update(of=('self',)).select_related('student__department')
               .get(pk=req_id))
        transition = CHAIN.find(user, req, req.status, action)
        remarks = (remarks or '').strip()
        if transition.remarks_required and not remarks:
            raise ValidationError({'remarks': 'Remarks are required for this action, so the reason is on record.'})
        if check := CHECKS.get((transition.action, transition.source)):
            check(req)
        change = InternshipStatusChange.objects.create(
            request=req, from_status=transition.source, to_status=transition.target, action=transition.action,
            remarks=remarks, changed_by=user, role=user.role)
        req.status = transition.target
        fields = ['status', 'updated_at']
        if transition.action == 'submit':
            req.submitted_at = timezone.now()
            fields.append('submitted_at')
        req.save(update_fields=fields)
        if after := AFTER.get((transition.action, transition.source)):
            after(req, user)
        record(AuditAction.WORKFLOW_ACTION, request=request, actor=user, target=req, action=transition.action,
               from_status=transition.source, to_status=transition.target, remarks=remarks)
        label = change.get_to_status_display()
        notify([req.student], f'Your internship request {req.pk} {STUDENT_PHRASE.get(req.status, f"is at {label}")}',
               remarks, f'/internships/{req.pk}', email=req.status in STUDENT_EMAIL)
        notify(queue_recipients(req, req.status).exclude(pk=user.pk),
               f'Internship request {req.pk} is waiting for you ({label})',
               f'{req.student.full_name} ({req.organisation}) has reached {label} and is in your ASIMS queue.',
               f'/internship-review/{req.pk}')
    return req
