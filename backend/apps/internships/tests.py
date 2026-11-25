"""Internship requests: the student's form, the shared company list and the request chain up to approval."""
import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import Department, Program, Role
from apps.accounts.tests import auth_as, make_user
from apps.audit.models import AuditAction, AuditLog
from apps.workflow.engine import WorkflowError

from .models import Company, Internship
from .workflow import RUNNER

REQUESTS = '/api/v1/internships/requests/'
COMPANIES = '/api/v1/internships/companies/'


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def people(db):
    cs = Department.objects.create(name='Computer Science', code='CS')
    se = Department.objects.create(name='Software Engineering', code='SE')
    bscs = Program.objects.create(department=cs, name='BS Computer Science')
    return {
        'cs': cs, 'bscs': bscs, 'bsse': Program.objects.create(department=se, name='BS Software Engineering'),
        'student': make_user(Role.STUDENT, 'ali@students.au.edu.pk', department=cs, program=bscs),
        'other_student': make_user(Role.STUDENT, 'sara@students.au.edu.pk', department=cs),
        'dic': make_user(Role.DIC, 'dic.cs@au.edu.pk', department=cs),
        'dic_se': make_user(Role.DIC, 'dic.se@au.edu.pk', department=se),
        'placement': make_user(Role.PLACEMENT_OFFICER),
        'admin': make_user(Role.ADMINISTRATOR),
    }


@pytest.fixture
def company(people):
    return Company.objects.create(name='Systems Ltd', address='Lahore', contact_phone='042-111', added_by=people['dic'])


def complete(company, **over):
    return {'semester': 7, 'company': company.pk, 'start_date': '2026-12-01', 'duration_weeks': 8,
            'mode': 'on_site', **over}


def submitted(api, people, company):
    """A complete request submitted to the DIC by the student; returns its id."""
    auth_as(api, people['student'])
    internship_id = api.post(REQUESTS, complete(company), format='json').json()['id']
    assert api.post(f'{REQUESTS}{internship_id}/submit/', format='json').status_code == 200
    return internship_id


def stage(internship_id):
    return Internship.objects.get(pk=internship_id).status


# ---------- the student's request ----------

def test_student_starts_a_request_with_the_program_from_their_profile(api, people, company):
    auth_as(api, people['student'])
    response = api.post(REQUESTS, {'company': company.pk}, format='json')
    assert response.status_code == 201
    data = response.json()
    assert data['program_name'] == 'BS Computer Science' and data['status'] == 'draft'
    assert data['reference'] == f'INT-{timezone.localdate():%Y}-{data["id"]:04d}'
    assert data['company_detail']['name'] == 'Systems Ltd'
    assert AuditLog.objects.filter(action=AuditAction.INTERNSHIP_CREATED).count() == 1


def test_only_one_open_request_at_a_time(api, people, company):
    auth_as(api, people['student'])
    first = api.post(REQUESTS, {}, format='json').json()['id']
    assert api.post(REQUESTS, {}, format='json').status_code == 400
    Internship.objects.filter(pk=first).update(status='rejected')
    assert api.post(REQUESTS, {}, format='json').status_code == 201  # a new one after a rejection


@pytest.mark.parametrize('field, value', [('program', 'bsse'), ('duration_weeks', 5), ('duration_weeks', 27),
                                          ('semester', 13), ('mode', 'abroad')])
def test_request_fields_are_checked(api, people, company, field, value):
    auth_as(api, people['student'])
    value = people[value].pk if field == 'program' else value
    response = api.post(REQUESTS, complete(company, **{field: value}), format='json')
    assert response.status_code == 400 and field in response.json()


def test_an_incomplete_request_cannot_be_submitted(api, people):
    auth_as(api, people['student'])
    internship_id = api.post(REQUESTS, {'semester': 7}, format='json').json()['id']
    response = api.post(f'{REQUESTS}{internship_id}/submit/', format='json')
    assert response.status_code == 400
    assert set(response.json()) == {'company', 'start_date', 'duration_weeks', 'mode'}
    assert stage(internship_id) == 'draft'


def test_submitted_request_is_locked_and_private(api, people, company):
    internship_id = submitted(api, people, company)
    internship = Internship.objects.get(pk=internship_id)
    assert internship.status == 'dic_review' and internship.submitted_at is not None
    assert api.patch(f'{REQUESTS}{internship_id}/', {'semester': 8}, format='json').status_code == 400
    auth_as(api, people['other_student'])
    assert api.get(f'{REQUESTS}{internship_id}/').status_code == 404


# ---------- the chain ----------

def test_dic_forwards_and_placement_approves(api, people, company):
    internship_id = submitted(api, people, company)
    RUNNER.perform(internship_id, 'forward', people['dic'])
    RUNNER.perform(internship_id, 'approve', people['placement'], remarks='Approved.')
    history = Internship.objects.get(pk=internship_id).status_history.all()
    assert [(h.action, h.to_status, h.role) for h in history] == [
        ('submit', 'dic_review', 'student'), ('forward', 'placement_approval', 'dic'),
        ('approve', 'approved', 'placement_officer')]
    assert AuditLog.objects.filter(action=AuditAction.WORKFLOW_ACTION).count() == 3


@pytest.mark.parametrize('who, action', [('dic_se', 'forward'), ('placement', 'forward'), ('student', 'forward'),
                                         ('admin', 'forward')])
def test_only_the_dic_of_the_department_forwards(api, people, company, who, action):
    internship_id = submitted(api, people, company)
    with pytest.raises(WorkflowError) as exc:
        RUNNER.perform(internship_id, action, people[who])
    assert exc.value.code == 'forbidden'


def test_returned_request_is_corrected_and_submitted_again(api, people, company):
    internship_id = submitted(api, people, company)
    with pytest.raises(ValidationError):
        RUNNER.perform(internship_id, 'return', people['dic'])  # remarks are required
    RUNNER.perform(internship_id, 'return', people['dic'], remarks='The start date is wrong.')
    response = api.get(f'{REQUESTS}{internship_id}/').json()
    assert response['status_label'] == 'Returned to student'
    assert response['status_history'][-1]['remarks'] == 'The start date is wrong.'

    assert api.patch(f'{REQUESTS}{internship_id}/', {'start_date': '2026-12-15'}, format='json').status_code == 200
    resubmitted = api.post(f'{REQUESTS}{internship_id}/submit/', {'remarks': 'Date fixed.'}, format='json')
    assert resubmitted.json()['status'] == 'dic_review'
    assert resubmitted.json()['status_history'][-1]['action'] == 'resubmit'


@pytest.mark.parametrize('who', ['placement', 'admin'])
def test_placement_or_administrator_returns_or_rejects(api, people, company, who):
    internship_id = submitted(api, people, company)
    RUNNER.perform(internship_id, 'forward', people['dic'])
    RUNNER.perform(internship_id, 'reject', people[who], remarks='Not an approved field.')
    assert stage(internship_id) == 'rejected'
    with pytest.raises(WorkflowError):
        RUNNER.perform(internship_id, 'approve', people['placement'])  # a rejection is final


# ---------- companies ----------

def test_students_add_companies_and_names_are_unique(api, people, company):
    auth_as(api, people['student'])
    added = api.post(COMPANIES, {'name': 'Arbisoft', 'address': 'Lahore', 'contact_phone': '042-222',
                                 'contact_person': 'HR Manager'}, format='json')
    assert added.status_code == 201
    duplicate = api.post(COMPANIES, {'name': ' systems ltd ', 'address': 'X', 'contact_phone': '1'}, format='json')
    assert duplicate.status_code == 400 and 'name' in duplicate.json()
    assert [c['name'] for c in api.get(COMPANIES, {'search': 'arbi'}).json()] == ['Arbisoft']
    assert Company.objects.get(name='Arbisoft').added_by == people['student']


def test_only_placement_corrects_a_company(api, people, company):
    auth_as(api, people['student'])
    assert api.patch(f'{COMPANIES}{company.pk}/', {'address': 'Karachi'}, format='json').status_code == 403
    auth_as(api, people['placement'])
    assert api.patch(f'{COMPANIES}{company.pk}/', {'address': 'Karachi'}, format='json').status_code == 200
    assert AuditLog.objects.filter(action=AuditAction.COMPANY_CHANGED, details__change='updated').exists()


def test_other_roles_cannot_use_the_company_list(api, people):
    auth_as(api, make_user(Role.FINANCE_OFFICER))
    assert api.get(COMPANIES).status_code == 403
