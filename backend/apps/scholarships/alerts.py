"""Who hears about a case when it moves: the student (in the app, at every stage) and the staff whose queue it
has just entered (in the app and by email). Key student emails are sent by emails.notify_student."""
from apps.accounts.models import Role, User
from apps.notifications.service import notify

from .choices import ApplicationStatus as S

# The role that has work to do when a case reaches each stage
QUEUE_ROLE = {
    S.PLACEMENT_VERIFICATION: Role.PLACEMENT_OFFICER,
    S.DAC_REVIEW: Role.DAC_MEMBER,
    S.AWAITING_FORWARDING: Role.PLACEMENT_OFFICER,
    S.DIRECTOR_REVIEW: Role.DIRECTOR,
    S.REGISTRAR_REVIEW: Role.REGISTRAR,
    S.VC_REVIEW: Role.VICE_CHANCELLOR,
    S.AWAITING_FEE_ADJUSTMENT: Role.FINANCE_OFFICER,
}


# How each stage reads in the student's notification: "Your application 7 ..."
STUDENT_PHRASE = {
    S.PLACEMENT_VERIFICATION: 'is with the Placement Office for verification',
    S.RETURNED: 'was returned to you for corrections',
    S.DAC_REVIEW: 'is with the Departmental Admission Committee',
    S.AWAITING_FORWARDING: 'was shortlisted by the Departmental Admission Committee',
    S.DIRECTOR_REVIEW: 'is with the Director',
    S.REGISTRAR_REVIEW: 'is with the Registrar',
    S.VC_REVIEW: 'is with the Vice Chancellor',
    S.AWAITING_FEE_ADJUSTMENT: 'was approved by the Vice Chancellor',
    S.COMPLETED: 'is complete: your fee has been adjusted',
    S.REJECTED: 'was not approved',
}


def queue_recipients(app, stage):
    """Active staff whose queue the case has entered (DAC members only of the student's department)."""
    role = QUEUE_ROLE.get(stage)
    if role is None:
        return User.objects.none()
    people = User.objects.filter(role=role, is_active=True)
    if role == Role.DAC_MEMBER:
        people = people.filter(department_id=app.student.department_id)
    return people


def case_moved(app, change, actor):
    label = change.get_to_status_display()
    student_body = change.remarks if change.remarks and change.action != 'submit' else ''
    phrase = STUDENT_PHRASE.get(change.to_status, f'is now at {label}')
    notify([app.student], f'Your application {app.pk} {phrase}', student_body,
           f'/scholarships/{app.pk}/status', email=False)
    staff = queue_recipients(app, change.to_status).exclude(pk=actor.pk)
    department = app.student.department.name if app.student.department else 'no department'
    notify(staff, f'Application {app.pk} is waiting for you ({label})',
           f'{app.applicant_name} ({department}, {app.cycle.name}) has reached {label} and is in your ASIMS queue.',
           f'/review/{app.pk}')


def signed_letter_ready(app):
    notify([app.student], 'Your signed award letter is ready',
           'The Placement Office has issued the signed copy of your award letter. You can download it from your '
           'application status page.', f'/scholarships/{app.pk}/status')
