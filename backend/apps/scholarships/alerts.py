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
    notify([app.student], f'Your application {app.pk} is now at {label}', student_body,
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
