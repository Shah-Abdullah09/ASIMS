"""Director, Registrar and Vice Chancellor approvals, and the student emails (Phase 3 step 4)."""
import pytest
from django.core import mail

from apps.accounts.models import Role

from .models import Application, ApplicationDocument
from .test_review import (REVIEW, STUDENT_BASE, act, client_for, cs, cycle, make_complete, make_user,  # noqa: F401
                          officer, submitted_application, temp_media)

APPROVERS = [('director', Role.DIRECTOR, 'director_review'), ('registrar', Role.REGISTRAR, 'registrar_review'),
             ('vc', Role.VICE_CHANCELLOR, 'vc_review')]


@pytest.fixture
def approvers(db):
    return {key: client_for(make_user(f'{key}@au.edu.pk', role=role, name=key.title())) for key, role, _ in APPROVERS}


@pytest.fixture
def case(cycle, cs):
    """(student client, id) of a CS case forwarded to the Director with a 60% DAC recommendation."""
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    Application.objects.filter(pk=app_id).update(status='director_review', scholarship_percentage=60,
                                                 interview_remarks='Genuine need.')
    return student_api, app_id


def at(app_id, stage):
    Application.objects.filter(pk=app_id).update(status=stage)


def ids(client):
    return [r['id'] for r in client.get(REVIEW).json()['results']]


# ---------- queues ----------

@pytest.mark.parametrize('key,role,stage', APPROVERS)
def test_each_approver_sees_only_its_own_stage(case, approvers, key, role, stage):
    _, app_id = case
    for other_stage in ['placement_verification', 'dac_review', 'awaiting_forwarding', 'director_review',
                        'registrar_review', 'vc_review', 'awaiting_fee_adjustment', 'rejected']:
        at(app_id, other_stage)
        assert ids(approvers[key]) == ([app_id] if other_stage == stage else []), (key, other_stage)


def test_approver_sees_the_whole_case_and_its_files(case, approvers):
    _, app_id = case
    data = approvers['director'].get(f'{REVIEW}{app_id}/').json()
    assert data['scholarship_percentage'] == 60 and data['interview_remarks'] == 'Genuine need.'
    assert [(a['action'], a['percentage'], a['remarks_required']) for a in data['available_actions']] == [
        ('approve', 'optional', False), ('reject', None, True)]
    url = next(d for d in data['documents'] if d['slot'] == 'domicile')['files'][0]['download_url']
    assert approvers['director'].get(url).status_code == 200
    assert approvers['registrar'].get(url).status_code == 404  # not at Registrar review yet


# ---------- decisions ----------

def test_approvals_pass_the_case_up_and_may_change_the_percentage(case, approvers):
    student_api, app_id = case
    r = act(approvers['director'], app_id, 'approve', 'Reduce to half.', percentage=50)
    assert r.status_code == 200 and r.json()['left_queue'] and r.json()['status'] == 'registrar_review'
    assert act(approvers['registrar'], app_id, 'approve').status_code == 200
    final = act(approvers['vc'], app_id, 'approve', 'Approved.').json()
    assert final['status'] == 'awaiting_fee_adjustment' and final['status_label'] == 'Awaiting fee adjustment'
    app = Application.objects.get(pk=app_id)
    assert app.scholarship_percentage == 50
    mine = student_api.get(f'{STUDENT_BASE}{app_id}/').json()
    assert mine['scholarship_percentage'] == 50
    assert [(h['action'], h['changed_by_role'], h['percentage']) for h in mine['status_history'][-3:]] == [
        ('approve', 'Director', 50), ('approve', 'Registrar', None), ('approve', 'Vice Chancellor', None)]


def test_approvers_cannot_act_out_of_turn(case, approvers):
    _, app_id = case
    assert act(approvers['registrar'], app_id, 'approve').status_code == 404  # not in the Registrar's queue
    assert act(approvers['vc'], app_id, 'reject', 'No.').status_code == 404
    act(approvers['director'], app_id, 'approve')
    assert act(approvers['director'], app_id, 'approve').status_code == 404  # already moved on


@pytest.mark.parametrize('key,role,stage', APPROVERS)
def test_reject_needs_remarks_and_ends_the_case(case, approvers, key, role, stage):
    _, app_id = case
    at(app_id, stage)
    assert act(approvers[key], app_id, 'reject', ' ').status_code == 400
    assert act(approvers[key], app_id, 'reject', 'Funds are exhausted for this cycle.').status_code == 200
    assert Application.objects.get(pk=app_id).status == 'rejected'


def test_percentage_range_is_checked_for_approvers(case, approvers):
    _, app_id = case
    assert act(approvers['director'], app_id, 'approve', percentage=0).status_code == 400
    assert act(approvers['director'], app_id, 'approve', percentage=100).status_code == 200


# ---------- emails to the student ----------

def run(callbacks, *steps):
    with callbacks(execute=True):
        for step in steps:
            response = step()
            assert response.status_code == 200, response.json()


def test_vc_approval_emails_the_student_with_the_percentage(case, approvers, django_capture_on_commit_callbacks):
    _, app_id = case
    mail.outbox.clear()
    run(django_capture_on_commit_callbacks,
        lambda: act(approvers['director'], app_id, 'approve', percentage=55),
        lambda: act(approvers['registrar'], app_id, 'approve'))
    assert mail.outbox == []  # no email for steps in between
    run(django_capture_on_commit_callbacks, lambda: act(approvers['vc'], app_id, 'approve'))
    (message,) = mail.outbox
    assert message.to == ['ali@gmail.com'] and 'approved' in message.subject
    assert '55% of the semester tuition fee' in message.body and 'Vice Chancellor' in message.body


def test_rejection_email_names_the_stage_and_remarks(case, approvers, django_capture_on_commit_callbacks):
    _, app_id = case
    mail.outbox.clear()
    run(django_capture_on_commit_callbacks,
        lambda: act(approvers['director'], app_id, 'reject', 'Family owns two houses.'))
    (message,) = mail.outbox
    assert 'not approved at Director review' in message.body and 'Family owns two houses.' in message.body


def test_not_shortlisted_email(cycle, cs, django_capture_on_commit_callbacks):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    at(app_id, 'dac_review')
    dac = client_for(make_user('dac@au.edu.pk', role=Role.DAC_MEMBER, dept=cs))
    mail.outbox.clear()
    run(django_capture_on_commit_callbacks, lambda: act(dac, app_id, 'not_shortlisted', 'Income above the limit.'))
    (message,) = mail.outbox
    assert 'was not shortlisted by the Departmental Admission Committee' in message.body
    assert 'Income above the limit.' in message.body


def test_return_email_lists_what_to_fix(cycle, cs, officer, django_capture_on_commit_callbacks):
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    make_complete(student_api, officer, app_id)
    officer.post(f'{REVIEW}{app_id}/flags/', {'section': 'income', 'note': 'Net pay missing.'}, format='json')
    domicile = ApplicationDocument.objects.get(application_id=app_id, slot='domicile')
    officer.post(f'{REVIEW}{app_id}/documents/{domicile.pk}/review/',
                 {'review_status': 'needs_clarification', 'note': 'Stamp not readable.'}, format='json')
    mail.outbox.clear()
    run(django_capture_on_commit_callbacks, lambda: act(officer, app_id, 'return', 'Please fix two things.'))
    (message,) = mail.outbox
    assert 'returned for corrections' in message.subject
    for text in ['Reason: Please fix two things.', '- Income: Net pay missing.', 'Stamp not readable.',
                 'Domicile']:
        assert text in message.body


def test_a_mail_failure_does_not_undo_the_decision(case, approvers, django_capture_on_commit_callbacks,
                                                   monkeypatch):
    _, app_id = case
    at(app_id, 'vc_review')

    def broken(*args, **kwargs):
        raise ConnectionError('SMTP down')

    monkeypatch.setattr('apps.scholarships.emails.send_mail', broken)
    run(django_capture_on_commit_callbacks, lambda: act(approvers['vc'], app_id, 'approve'))
    assert Application.objects.get(pk=app_id).status == 'awaiting_fee_adjustment'
