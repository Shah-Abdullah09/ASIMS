from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User

from .models import Application, ScholarshipCycle, StatusChange
from .test_submission import fill_complete, pdf

PASSWORD = 'Str0ng-Passw0rd!'
STUDENT_BASE = '/api/v1/scholarships/applications/'
REVIEW = '/api/v1/scholarships/review/applications/'


@pytest.fixture(autouse=True)
def temp_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def cs(db):
    return Department.objects.create(name='Computer Science', code='CS')


@pytest.fixture
def ee(db):
    return Department.objects.create(name='Electrical Engineering', code='EE')


@pytest.fixture
def cycle(db):
    today = timezone.localdate()
    return ScholarshipCycle.objects.create(name='Fall-26', opens_on=today - timedelta(days=1),
                                           closes_on=today + timedelta(days=30))


def make_user(email, role=Role.STUDENT, dept=None, name='Ali Khan', **extra):
    return User.objects.create_user(email=email, password=PASSWORD, full_name=name, role=role, department=dept,
                                    is_email_verified=True, **extra)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def officer(cs):
    return client_for(make_user('placement@au.edu.pk', role=Role.PLACEMENT_OFFICER, dept=cs, name='Sana Placement'))


def submitted_application(cycle, dept, email, name='Ali Khan', registration_id='233585', cnic='36302-1234567-1'):
    """A fully filled and submitted application for a new student."""
    student = make_user(email, dept=dept, name=name, registration_id=registration_id)
    api = client_for(student)
    app_id = api.post(STUDENT_BASE, {'cycle': cycle.pk}, format='json').json()['id']
    fill_complete(api, app_id, cnic=cnic)
    api.patch(f'{STUDENT_BASE}{app_id}/sections/undertaking/', {'undertaking_name': name}, format='json')
    response = api.post(f'{STUDENT_BASE}{app_id}/submit/')
    assert response.status_code == 200, response.json()
    return api, app_id


def make_complete(student_api, officer, app_id):
    """Upload the Form 2 scan and have the office receive the original."""
    decl_id = student_api.get(f'{STUDENT_BASE}{app_id}/declarations/').json()[0]['id']
    student_api.post(f'{STUDENT_BASE}{app_id}/declarations/{decl_id}/scan/', {'file': pdf()}, format='multipart')
    officer.post(f'/api/v1/scholarships/declarations/{decl_id}/receive/', {}, format='json')


def verify_documents(officer, app_id):
    """Placement marks every uploaded file Verified."""
    for slot in officer.get(f'{REVIEW}{app_id}/').json()['documents']:
        for f in slot['files']:
            response = officer.post(f"{REVIEW}{app_id}/documents/{f['id']}/review/", {'review_status': 'verified'},
                                    format='json')
            assert response.status_code == 200, response.json()


def ready_for_dac(student_api, officer, app_id):
    make_complete(student_api, officer, app_id)
    verify_documents(officer, app_id)


def act(client, app_id, action, remarks='', **extra):
    return client.post(f'{REVIEW}{app_id}/actions/', {'action': action, 'remarks': remarks, **extra}, format='json')


# ---------- permissions ----------

@pytest.mark.parametrize('role', [Role.STUDENT, Role.DAC_MEMBER, Role.DIC, Role.FACULTY_SUPERVISOR, Role.DIRECTOR,
                                  Role.REGISTRAR, Role.VICE_CHANCELLOR, Role.FINANCE_OFFICER])
def test_only_placement_office_and_admin_can_review(cycle, cs, role):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    client = client_for(make_user(f'{role}@au.edu.pk', role=role, dept=cs))
    assert client.get(REVIEW).status_code == 403
    assert client.get(f'{REVIEW}{app_id}/').status_code == 403
    assert act(client, app_id, 'reject', 'No.').status_code == 403


def test_anonymous_gets_401(db):
    assert APIClient().get(REVIEW).status_code == 401


@pytest.mark.parametrize('role', [Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR])
def test_placement_officer_and_administrator_can_review(cycle, cs, role):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    client = client_for(make_user(f'{role}@au.edu.pk', role=role, dept=cs))
    assert client.get(REVIEW).json()['count'] == 1
    assert client.get(f'{REVIEW}{app_id}/').status_code == 200


# ---------- list, filters, search ----------

def test_drafts_are_not_shown_to_staff(cycle, cs, officer):
    student = make_user('draft@gmail.com', dept=cs)
    draft_id = client_for(student).post(STUDENT_BASE, {'cycle': cycle.pk}, format='json').json()['id']
    assert officer.get(REVIEW).json()['count'] == 0
    assert officer.get(f'{REVIEW}{draft_id}/').status_code == 404


def test_list_shows_key_columns_and_completion(cycle, cs, officer):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    row = officer.get(REVIEW).json()['results'][0]
    assert row['id'] == app_id and row['applicant_name'] == 'Ali Khan' and row['registration_id'] == '233585'
    assert row['department'] == 'Computer Science' and row['cycle_name'] == 'Fall-26'
    assert row['status'] == 'placement_verification' and row['status_label'] == 'Placement verification'
    assert row['completion']['form_submitted'] and not row['completion']['complete']


@pytest.fixture
def three_applications(cycle, cs, ee, officer):
    """Ali (CS, complete, verified to DAC), Sara (CS, incomplete), Bilal (EE, incomplete, Spring cycle)."""
    ali_api, ali = submitted_application(cycle, cs, 'ali@gmail.com', 'Ali Khan', '233585', '36302-1234567-1')
    ready_for_dac(ali_api, officer, ali)
    assert act(officer, ali, 'verify').status_code == 200
    _, sara = submitted_application(cycle, cs, 'sara@gmail.com', 'Sara Ahmed', '2335901', '36302-7654321-2')
    spring = ScholarshipCycle.objects.create(name='Spring-27', opens_on=cycle.opens_on, closes_on=cycle.closes_on)
    _, bilal = submitted_application(spring, ee, 'bilal@gmail.com', 'Bilal Raza', '24400012', '36302-1111222-3')
    return {'ali': ali, 'sara': sara, 'bilal': bilal, 'fall': cycle.pk, 'spring': spring.pk}


def ids(officer, query):
    return sorted(row['id'] for row in officer.get(f'{REVIEW}?{query}').json()['results'])


def test_filters(three_applications, officer, cs, ee):
    a = three_applications
    assert ids(officer, f"cycle={a['fall']}") == sorted([a['ali'], a['sara']])
    assert ids(officer, f"department={ee.pk}") == [a['bilal']]
    assert ids(officer, 'status=dac_review') == [a['ali']]
    assert ids(officer, 'status=placement_verification') == sorted([a['sara'], a['bilal']])
    assert ids(officer, 'complete=true') == [a['ali']]
    assert ids(officer, 'complete=false') == sorted([a['sara'], a['bilal']])
    assert ids(officer, f"cycle={a['fall']}&complete=false") == [a['sara']]


@pytest.mark.parametrize('term,who', [('sara', 'sara'), ('BILAL', 'bilal'), ('2335901', 'sara'),
                                      ('36302-1234567', 'ali'), ('bilal@gmail', 'bilal')])
def test_search_by_name_registration_id_cnic_or_email(three_applications, officer, term, who):
    assert ids(officer, f'search={term}') == [three_applications[who]]


def test_ordering(three_applications, officer):
    names = [r['applicant_name'] for r in officer.get(f'{REVIEW}?ordering=applicant_name').json()['results']]
    assert names == ['Ali Khan', 'Bilal Raza', 'Sara Ahmed']


# ---------- detail ----------

def test_detail_has_answers_documents_declarations_and_history(cycle, cs, officer):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    data = officer.get(f'{REVIEW}{app_id}/').json()
    assert data['student']['email'] == 'ali@gmail.com' and data['student']['department'] == 'Computer Science'
    assert data['parents'][0]['name'] == 'Muhammad Aslam'
    assert data['summary']['total_monthly_income'] == 72000
    domicile = next(d for d in data['documents'] if d['slot'] == 'domicile')
    assert len(domicile['files']) == 1 and officer.get(domicile['files'][0]['download_url']).status_code == 200
    assert data['declarations'][0]['person'] == 'Father'
    first = data['status_history'][0]
    assert (first['from_status'], first['to_status'], first['action']) == ('draft', 'placement_verification', 'submit')
    assert first['remarks'] == 'Submitted by the student.' and first['changed_by_role'] == 'Student'
    assert [a['action'] for a in data['available_actions']] == ['verify', 'return', 'reject']


# ---------- Placement actions (the full chain is tested in test_workflow.py) ----------

def test_action_is_recorded_and_visible_to_the_student(cycle, cs, officer):
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    response = act(officer, app_id, 'reject', 'Family income above the limit.')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'rejected' and data['review_remarks'] == 'Family income above the limit.'
    assert data['reviewed_by'] == 'Sana Placement' and data['reviewed_at'] and data['available_actions'] == []

    student_view = student_api.get(f'{STUDENT_BASE}{app_id}/').json()
    assert student_view['status'] == 'rejected' and student_view['status_label'] == 'Rejected'
    history = student_view['status_history']
    assert [(h['from_status'], h['to_status']) for h in history] == [('draft', 'placement_verification'),
                                                                      ('placement_verification', 'rejected')]
    assert history[1]['action'] == 'reject' and history[1]['remarks'] == 'Family income above the limit.'
    assert history[1]['changed_by'] == 'Sana Placement' and history[1]['changed_by_role'] == 'Placement Officer'


def test_rejection_needs_remarks(cycle, cs, officer):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    response = act(officer, app_id, 'reject', '   ')
    assert response.status_code == 400 and 'remarks' in response.json()
    assert act(officer, app_id, 'reject', 'Family income above the limit.').status_code == 200


def test_verify_needs_a_complete_application(cycle, cs, officer):
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    response = act(officer, app_id, 'verify')
    assert response.status_code == 400 and 'Form 2 scan' in str(response.json())
    ready_for_dac(student_api, officer, app_id)
    assert act(officer, app_id, 'verify', 'Documents checked.').json()['status'] == 'dac_review'


def test_unknown_or_out_of_stage_actions_are_refused(cycle, cs, officer):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    assert act(officer, app_id, 'maybe').status_code == 400
    response = act(officer, app_id, 'forward')  # forwarding comes after the DAC
    assert response.status_code == 409 and response.json()['code'] == 'stage_conflict'
    assert act(officer, app_id, 'submit').status_code == 409  # submitting starts from a draft
    assert Application.objects.get(pk=app_id).status == 'placement_verification'


def test_a_rejected_case_is_final(cycle, cs, officer):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    act(officer, app_id, 'reject', 'Wrong file.')
    assert act(officer, app_id, 'verify').status_code == 409
    assert StatusChange.objects.filter(application_id=app_id).count() == 2  # submit + reject


def test_student_still_cannot_edit_after_a_decision(cycle, cs, officer):
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    act(officer, app_id, 'reject', 'Incomplete income proof.')
    assert student_api.patch(f'{STUDENT_BASE}{app_id}/sections/personal/', {'domicile': 'X'},
                             format='json').status_code == 403


# ---------- cycles for the filter ----------

def test_staff_see_every_cycle_for_filtering(cycle, cs, officer):
    ScholarshipCycle.objects.create(name='Spring-26', opens_on='2026-02-01', closes_on='2026-03-01')
    names = [c['name'] for c in officer.get('/api/v1/scholarships/cycles/').json()]
    assert names == ['Fall-26', 'Spring-26']  # closed cycles included, newest first
    student = client_for(make_user('s@gmail.com', dept=cs))
    assert student.get('/api/v1/scholarships/cycles/').status_code == 403
