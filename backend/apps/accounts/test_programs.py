"""Programs of a department: the Administrator's list, the registration choice and the department rule."""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog

from .models import Department, Program, Role, User
from .tests import auth_as, make_user, register


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def dept(db):
    return Department.objects.create(name='Computer Science', code='CS')


@pytest.fixture
def programs(dept):
    other = Department.objects.create(name='Software Engineering', code='SE')
    return {'bscs': Program.objects.create(department=dept, name='BS Computer Science'),
            'old': Program.objects.create(department=dept, name='BS Old', is_active=False),
            'bsse': Program.objects.create(department=other, name='BS Software Engineering')}


def test_public_program_list_shows_active_programs_of_one_department(api, dept, programs):
    assert [p['name'] for p in api.get('/api/v1/programs/', {'department': dept.pk}).json()] == ['BS Computer Science']
    assert len(api.get('/api/v1/programs/').json()) == 2
    assert api.get('/api/v1/programs/', {'department': 'x'}).json() == []


def test_student_registers_into_a_program_of_their_department(api, dept, programs):
    assert register(api, dept, program=programs['bscs'].pk).status_code == 201
    assert User.objects.get(email__startswith='ali@').program == programs['bscs']


@pytest.mark.parametrize('key', ['bsse', 'old'])
def test_registration_rejects_a_program_of_another_department_or_inactive(api, dept, programs, key):
    response = register(api, dept, program=programs[key].pk)
    assert response.status_code == 400 and 'program' in response.json()


def test_program_is_optional_at_registration(api, dept):
    assert register(api, dept).status_code == 201


def test_admin_adds_and_deactivates_programs_with_audit(api, dept):
    auth_as(api, make_user(Role.ADMINISTRATOR))
    created = api.post('/api/v1/admin/programs/', {'department': dept.pk, 'name': 'BS Data Science'}, format='json')
    assert created.status_code == 201 and created.json()['department_name'] == 'Computer Science'
    duplicate = api.post('/api/v1/admin/programs/', {'department': dept.pk, 'name': 'BS Data Science'}, format='json')
    assert duplicate.status_code == 400

    program_id = created.json()['id']
    assert api.patch(f'/api/v1/admin/programs/{program_id}/', {'is_active': False}, format='json').status_code == 200
    assert api.delete(f'/api/v1/admin/programs/{program_id}/').status_code == 405
    changes = AuditLog.objects.filter(action=AuditAction.PROGRAM_CHANGED).values_list('details__change', flat=True)
    assert sorted(changes) == ['created', 'updated']


@pytest.mark.parametrize('role', [Role.PLACEMENT_OFFICER, Role.STUDENT])
def test_only_the_administrator_manages_programs(api, dept, role):
    auth_as(api, make_user(role, department=dept))
    assert api.get('/api/v1/admin/programs/').status_code == 403


def test_admin_cannot_give_a_student_a_program_of_another_department(api, dept, programs):
    auth_as(api, make_user(Role.ADMINISTRATOR))
    student = make_user(Role.STUDENT, department=dept, program=programs['bscs'])
    wrong = api.patch(f'/api/v1/admin/users/{student.pk}/', {'program': programs['bsse'].pk}, format='json')
    assert wrong.status_code == 400 and 'program' in wrong.json()

    moved = api.patch(f'/api/v1/admin/users/{student.pk}/', {'department': programs['bsse'].department_id,
                                                              'program': programs['bsse'].pk}, format='json')
    assert moved.status_code == 200
    auth_as(api, User.objects.get(pk=student.pk))
    assert api.get('/api/v1/auth/me/').json()['program_name'] == 'BS Software Engineering'
