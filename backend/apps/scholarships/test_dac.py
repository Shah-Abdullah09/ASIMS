"""DAC review and Placement forwarding (Phase 3 step 3)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditLog

from .models import Application, ScholarshipCycle
from .test_review import (REVIEW, STUDENT_BASE, act, client_for, cs, cycle, ee, make_user, officer,  # noqa: F401
                          submitted_application, temp_media)


def at(app_id, stage):
    Application.objects.filter(pk=app_id).update(status=stage)


@pytest.fixture
def dac(cs):
    return client_for(make_user('dac.cs@au.edu.pk', role=Role.DAC_MEMBER, dept=cs, name='Dr Cs'))


@pytest.fixture
def dac_ee(ee):
    return client_for(make_user('dac.ee@au.edu.pk', role=Role.DAC_MEMBER, dept=ee, name='Dr Ee'))


@pytest.fixture
def ali(cycle, cs):
    """(student client, id) of a CS application already verified by Placement (at DAC review)."""
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    at(app_id, 'dac_review')
    return student_api, app_id


def interview(client, app_id, date=None, remarks='Father is a clerk; family of five; genuine need.'):
    date = date or timezone.localdate().isoformat()
    return client.put(f'{REVIEW}{app_id}/interview/', {'interview_date': date, 'interview_remarks': remarks},
                      format='json')


def ids(client, query=''):
    return sorted(r['id'] for r in client.get(f'{REVIEW}?{query}').json()['results'])


# ---------- the DAC queue ----------

def test_dac_sees_only_its_department_at_dac_review(ali, dac, dac_ee, cycle, cs, ee):
    _, app_id = ali
    _, waiting = submitted_application(cycle, cs, 'sara@gmail.com', 'Sara Ahmed', '2335901', '36302-7654321-2')
    _, ee_case = submitted_application(cycle, ee, 'bilal@gmail.com', 'Bilal Raza', '24400012', '36302-1111222-3')
    at(ee_case, 'dac_review')
    assert ids(dac) == [app_id]  # Sara is still at Placement verification
    assert ids(dac_ee) == [ee_case]
    assert dac.get(f'{REVIEW}{waiting}/').status_code == 404
    assert dac.get(f'{REVIEW}{ee_case}/').status_code == 404


def test_dac_member_without_a_department_sees_nothing(ali):
    lost = client_for(make_user('dac.none@au.edu.pk', role=Role.DAC_MEMBER))
    assert ids(lost) == []


def test_dac_can_open_files_of_its_cases_only(ali, dac, dac_ee):
    _, app_id = ali
    detail = dac.get(f'{REVIEW}{app_id}/').json()
    url = next(d for d in detail['documents'] if d['slot'] == 'domicile')['files'][0]['download_url']
    assert dac.get(url).status_code == 200
    assert dac_ee.get(url).status_code == 404
    at(app_id, 'awaiting_forwarding')
    assert dac.get(url).status_code == 404  # left the DAC queue


@pytest.mark.parametrize('role', [Role.FINANCE_OFFICER, Role.STUDENT])
def test_other_roles_still_have_no_staff_queue(ali, cs, role):
    client = client_for(make_user(f'{role}.q@au.edu.pk', role=role, dept=cs))
    assert client.get(REVIEW).status_code == 403


# ---------- interview ----------

def test_interview_is_recorded_and_audited(ali, dac):
    _, app_id = ali
    response = interview(dac, app_id)
    assert response.status_code == 200
    data = response.json()
    assert data['interview_date'] == timezone.localdate().isoformat()
    assert data['interview_remarks'].startswith('Father is a clerk') and data['interview_recorded_by'] == 'Dr Cs'
    corrected = interview(dac, app_id, remarks='Corrected: family of six.').json()
    assert corrected['interview_remarks'] == 'Corrected: family of six.'
    assert AuditLog.objects.filter(action=AuditAction.INTERVIEW_RECORDED).count() == 2


def test_interview_date_not_in_the_future_and_remarks_required(ali, dac):
    _, app_id = ali
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    response = interview(dac, app_id, date=tomorrow)
    assert response.status_code == 400 and 'interview_date' in response.json()
    assert interview(dac, app_id, remarks='  ').status_code == 400


def test_only_the_departments_dac_records_the_interview(ali, dac_ee, officer):
    _, app_id = ali
    assert interview(dac_ee, app_id).status_code == 404
    assert interview(officer, app_id).status_code == 403


# ---------- shortlist / not shortlisted ----------

def test_shortlist_needs_the_interview_and_a_percentage(ali, dac):
    _, app_id = ali
    actions = dac.get(f'{REVIEW}{app_id}/').json()['available_actions']
    assert [(a['action'], a['percentage']) for a in actions] == [('shortlist', 'required'), ('not_shortlisted', None)]
    response = act(dac, app_id, 'shortlist', percentage=50)
    assert response.status_code == 400 and 'interview' in str(response.json())
    interview(dac, app_id)
    assert act(dac, app_id, 'shortlist').status_code == 400  # no percentage
    assert act(dac, app_id, 'shortlist', percentage=101).status_code == 400
    response = act(dac, app_id, 'shortlist', 'Recommended.', percentage=60)
    assert response.status_code == 200
    assert response.json() == {'id': app_id, 'status': 'awaiting_forwarding', 'status_label': 'Awaiting forwarding',
                               'left_queue': True, 'available_actions': []}
    assert dac.get(f'{REVIEW}{app_id}/').status_code == 404  # out of the DAC queue
    assert Application.objects.get(pk=app_id).status == 'awaiting_forwarding'
    assert Application.objects.get(pk=app_id).scholarship_percentage == 60


def test_not_shortlisted_ends_the_case_with_remarks(ali, dac):
    student_api, app_id = ali
    assert act(dac, app_id, 'not_shortlisted').status_code == 400
    assert act(dac, app_id, 'not_shortlisted', 'Family income is above the limit.').status_code == 200
    mine = student_api.get(f'{STUDENT_BASE}{app_id}/').json()
    assert mine['status'] == 'rejected' and mine['status_history'][-1]['remarks'] == 'Family income is above the limit.'


def test_student_does_not_see_interview_notes_or_the_percentage_before_approval(ali, dac, officer):
    student_api, app_id = ali
    interview(dac, app_id)
    act(dac, app_id, 'shortlist', 'Recommended.', percentage=60)
    mine = student_api.get(f'{STUDENT_BASE}{app_id}/').json()
    assert 'interview_remarks' not in mine and 'interview_recorded_by' not in mine
    assert mine['scholarship_percentage'] is None
    assert all(h['percentage'] is None for h in mine['status_history'])
    assert mine['status_label'] == 'Awaiting forwarding'
    staff = officer.get(f'{REVIEW}{app_id}/').json()
    assert staff['scholarship_percentage'] == 60 and staff['interview_remarks'].startswith('Father')
    at(app_id, 'awaiting_fee_adjustment')  # after the VC approves
    assert student_api.get(f'{STUDENT_BASE}{app_id}/').json()['scholarship_percentage'] == 60


# ---------- forwarding ----------

@pytest.fixture
def shortlisted(cycle, cs, dac):
    """Three CS cases shortlisted by the DAC: two in Fall-26, one in Spring-27."""
    spring = ScholarshipCycle.objects.create(name='Spring-27', opens_on=cycle.opens_on, closes_on=cycle.closes_on)
    made = []
    for c, email, name, reg, cnic in [(cycle, 'a@gmail.com', 'Ali Khan', '233585', '36302-1234567-1'),
                                      (cycle, 'b@gmail.com', 'Sara Ahmed', '2335901', '36302-7654321-2'),
                                      (spring, 'c@gmail.com', 'Bilal Raza', '24400012', '36302-1111222-3')]:
        _, app_id = submitted_application(c, cs, email, name, reg, cnic)
        at(app_id, 'dac_review')
        interview(dac, app_id)
        act(dac, app_id, 'shortlist', percentage=50)
        made.append(app_id)
    return made, spring


def test_forward_one_case(shortlisted, officer):
    (first, *_), _ = shortlisted
    assert act(officer, first, 'forward').json()['status'] == 'director_review'


def test_forward_all_needs_confirmation_and_can_be_limited_to_a_cycle(shortlisted, officer, cycle):
    made, spring = shortlisted
    url = f'{REVIEW}forward-all/'
    assert officer.post(url, {}, format='json').status_code == 400
    assert officer.post(url, {'confirm': False}, format='json').status_code == 400
    response = officer.post(url, {'confirm': True, 'cycle': cycle.pk}, format='json')
    assert response.status_code == 200 and response.json() == {'forwarded': made[:2], 'skipped': []}
    assert Application.objects.get(pk=made[2]).status == 'awaiting_forwarding'
    assert officer.post(url, {'confirm': True}, format='json').json() == {'forwarded': [made[2]], 'skipped': []}
    assert officer.post(url, {'confirm': True}, format='json').json() == {'forwarded': [], 'skipped': []}


def test_only_placement_forwards(shortlisted, dac):
    (first, *_), _ = shortlisted
    assert dac.post(f'{REVIEW}forward-all/', {'confirm': True}, format='json').status_code == 403
    assert act(dac, first, 'forward').status_code == 404  # not in the DAC queue any more
