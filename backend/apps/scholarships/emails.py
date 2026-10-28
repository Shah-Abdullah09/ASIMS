"""Emails to the student when the approval chain needs them or decides: returned for corrections,
not shortlisted or rejected, and approved by the Vice Chancellor. Staff emails come with notifications
(Phase 6). Sent after the decision is saved; a mail failure is logged and never undoes the decision."""
import logging

from django.core.mail import send_mail

from .choices import ApplicationStatus as S
from .choices import DocumentReview

log = logging.getLogger(__name__)


def _recipient(app):
    return app.email or app.student.email


def _returned(app, change):
    lines = [f'Reason: {change.remarks}', '']
    flags = list(app.flags.filter(resolved_at__isnull=True))
    unclear = list(app.documents.filter(review_status=DocumentReview.NEEDS_CLARIFICATION))
    if flags:
        lines.append('Sections to correct:')
        lines += [f'- {f.get_section_display()}: {f.note}' for f in flags]
    if unclear:
        lines.append('Documents to replace or clarify:')
        lines += [f'- {d.get_slot_display()} ({d.original_name}): {d.review_note}' for d in unclear]
    return (f'ASIMS: scholarship application #{app.pk} returned for corrections',
            f'Dear {app.applicant_name},\n\nThe Placement Office has returned your {app.cycle.name} need based '
            f'financial grant application (number {app.pk}) so you can correct a few things.\n\n'
            + '\n'.join(lines)
            + '\n\nOnly these parts can be changed. Make the corrections in ASIMS and resubmit the application.')


def _rejected(app, change):
    what = 'was not shortlisted by the Departmental Admission Committee' if change.action == 'not_shortlisted' \
        else f'was not approved at {change.get_from_status_display()}'
    return (f'ASIMS: decision on scholarship application #{app.pk}',
            f'Dear {app.applicant_name},\n\nWe regret to inform you that your {app.cycle.name} need based financial '
            f'grant application (number {app.pk}) {what}.\n\nRemarks: {change.remarks}\n\n'
            'This decision closes the application.')


def _approved(app, change):
    return (f'ASIMS: scholarship application #{app.pk} approved',
            f'Dear {app.applicant_name},\n\nYour {app.cycle.name} need based financial grant application '
            f'(number {app.pk}) has been approved by the Vice Chancellor.\n\n'
            f'Approved scholarship: {app.scholarship_percentage}% of the semester tuition fee.\n\n'
            'The Finance Office will now adjust your fee; you can follow this in ASIMS.')


EMAILS = {S.RETURNED: _returned, S.REJECTED: _rejected, S.AWAITING_FEE_ADJUSTMENT: _approved}


def notify_student(app, change):
    """Email the student if this stage change is one they are told about."""
    build = EMAILS.get(change.to_status)
    if build is None:
        return
    subject, body = build(app, change)
    try:
        send_mail(subject, body, None, [_recipient(app)])
    except Exception:  # the decision is saved; a mail outage must not turn it into an error
        log.exception('Could not email the student about application %s (%s)', app.pk, change.to_status)
