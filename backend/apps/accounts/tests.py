import re
from datetime import timedelta

import pytest
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import Department, Role, User

PASSWORD = 'Str0ng-Passw0rd!'
DOMAIN = 'students.au.edu.pk'


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def dept(db):
    return Department.objects.create(name='Computer Science', code='CS')


def make_user(role, email=None, department=None, verified=True, **extra):
    email = email or f'{role}@au.edu.pk'
    return User.objects.create_user(
        email=email, password=PASSWORD, full_name=role.title(), role=role,
        department=department, is_email_verified=verified, **extra,
    )


def login(api, email, password=PASSWORD):
    return api.post('/api/v1/auth/login/', {'email': email, 'password': password}, format='json')


def auth_as(api, user):
    token = login(api, user.email).json()['access']
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


def register(api, dept, **over):
    payload = {'email': f'ali@{DOMAIN}', 'full_name': 'Ali Khan', 'password': PASSWORD,
               'department': dept.pk, **over}
    return api.post('/api/v1/auth/register/', payload, format='json')


# ---------- registration and email verification ----------

def test_student_registers_verifies_and_logs_in(api, dept):
    assert register(api, dept).status_code == 201
    user = User.objects.get(email=f'ali@{DOMAIN}')
    assert user.role == Role.STUDENT and not user.is_email_verified

    blocked = login(api, user.email)
    assert blocked.status_code == 401  # cannot log in before verifying

    token = re.search(r'token=(\S+)', mail.outbox[0].body).group(1)
    assert api.post('/api/v1/auth/verify-email/', {'token': token}, format='json').status_code == 200

    ok = login(api, user.email)
    assert ok.status_code == 200
    assert ok.json()['user']['role'] == 'student'


def test_student_can_register_with_a_personal_email(api, dept):
    assert register(api, dept, email='Ali.Khan@gmail.com').status_code == 201
    user = User.objects.get(email='ali.khan@gmail.com')  # stored lowercase
    assert user.role == Role.STUDENT and not user.is_email_verified


def test_optional_domain_restriction_rejects_other_domains(api, dept, settings):
    settings.STUDENT_EMAIL_DOMAIN = DOMAIN
    response = register(api, dept, email='ali@gmail.com')
    assert response.status_code == 400
    assert 'email' in response.json()
    assert not User.objects.filter(email='ali@gmail.com').exists()
    assert register(api, dept).status_code == 201  # the configured domain still works


def test_registration_rejects_invalid_email_format(api, dept):
    assert register(api, dept, email='not-an-email').status_code == 400


def test_registration_rejects_duplicate_email(api, dept):
    assert register(api, dept).status_code == 201
    assert register(api, dept).status_code == 400


def test_registration_rejects_weak_password(api, dept):
    assert register(api, dept, password='12345678').status_code == 400


def test_registration_cannot_choose_a_role(api, dept):
    register(api, dept, role='administrator')
    assert User.objects.get(email=f'ali@{DOMAIN}').role == Role.STUDENT


def test_invalid_verification_token_is_rejected(api, db):
    response = api.post('/api/v1/auth/verify-email/', {'token': 'garbage'}, format='json')
    assert response.status_code == 400


def test_public_department_list_only_shows_active(api, dept):
    Department.objects.create(name='Old Dept', code='OLD', is_active=False)
    data = api.get('/api/v1/departments/').json()
    assert [d['code'] for d in data] == ['CS']


# ---------- login, tokens ----------

def test_wrong_password_is_rejected(api, db):
    make_user(Role.REGISTRAR)
    assert login(api, 'registrar@au.edu.pk', 'nope').status_code == 401


def test_deactivated_user_cannot_login(api, db):
    make_user(Role.REGISTRAR, is_active=False)
    assert login(api, 'registrar@au.edu.pk').status_code == 401


def test_login_returns_role_claim_and_refresh_works(api, db):
    make_user(Role.DIRECTOR)
    tokens = login(api, 'director@au.edu.pk').json()
    assert AccessToken(tokens['access'])['role'] == 'director'
    refreshed = api.post('/api/v1/auth/refresh/', {'refresh': tokens['refresh']}, format='json')
    assert refreshed.status_code == 200 and 'access' in refreshed.json()


def test_me_requires_authentication(api, db):
    assert api.get('/api/v1/auth/me/').status_code == 401


def test_expired_token_is_rejected(api, db):
    user = make_user(Role.DIRECTOR)
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=-timedelta(seconds=5))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    assert api.get('/api/v1/auth/me/').status_code == 401


def test_access_token_lifetime_is_24_hours(db):
    token = AccessToken.for_user(make_user(Role.DIRECTOR))
    assert token['exp'] - token['iat'] == 24 * 60 * 60


# ---------- role based access control ----------

@pytest.mark.parametrize('role', [r for r in Role.values if r != Role.ADMINISTRATOR])
def test_non_admin_roles_get_403_on_admin_routes(api, db, role):
    dept = Department.objects.create(name='X', code='X')
    user = make_user(role, department=dept)
    auth_as(api, user)
    assert api.get('/api/v1/admin/users/').status_code == 403
    assert api.get('/api/v1/admin/departments/').status_code == 403
    assert api.post('/api/v1/admin/departments/', {'name': 'N', 'code': 'N'}, format='json').status_code == 403


def test_anonymous_gets_401_on_admin_routes(api, db):
    assert api.get('/api/v1/admin/users/').status_code == 401


def test_administrator_can_list_users(api, db):
    admin = make_user(Role.ADMINISTRATOR)
    auth_as(api, admin)
    assert api.get('/api/v1/admin/users/').status_code == 200


# ---------- administrator management ----------

def test_admin_creates_department_and_staff_account(api, db):
    auth_as(api, make_user(Role.ADMINISTRATOR))
    created = api.post('/api/v1/admin/departments/', {'name': 'Software Engineering', 'code': 'SE'}, format='json')
    assert created.status_code == 201
    dept_id = created.json()['id']

    staff = api.post('/api/v1/admin/users/', {
        'email': 'dac.se@au.edu.pk', 'full_name': 'DAC SE', 'role': 'dac_member',
        'department': dept_id, 'password': PASSWORD}, format='json')
    assert staff.status_code == 201
    new_user = User.objects.get(email='dac.se@au.edu.pk')
    assert new_user.is_email_verified and new_user.check_password(PASSWORD)

    api.credentials()  # drop admin token
    assert login(api, 'dac.se@au.edu.pk').status_code == 200  # staff can log in straight away


@pytest.mark.parametrize('role', ['dac_member', 'dic'])
def test_department_roles_require_a_department(api, db, role):
    auth_as(api, make_user(Role.ADMINISTRATOR))
    response = api.post('/api/v1/admin/users/', {
        'email': 'x@au.edu.pk', 'full_name': 'X', 'role': role, 'password': PASSWORD}, format='json')
    assert response.status_code == 400 and 'department' in response.json()


def test_admin_can_deactivate_but_not_delete_users(api, db):
    auth_as(api, make_user(Role.ADMINISTRATOR))
    target = make_user(Role.FINANCE_OFFICER)
    assert api.patch(f'/api/v1/admin/users/{target.pk}/', {'is_active': False}, format='json').status_code == 200
    assert api.delete(f'/api/v1/admin/users/{target.pk}/').status_code == 405
    target.refresh_from_db()
    assert not target.is_active
    api.credentials()
    assert login(api, target.email).status_code == 401


def test_admin_can_reset_password(api, db):
    auth_as(api, make_user(Role.ADMINISTRATOR))
    target = make_user(Role.REGISTRAR)
    new_password = 'An0ther-Str0ng-Pass!'
    assert api.patch(f'/api/v1/admin/users/{target.pk}/', {'password': new_password}, format='json').status_code == 200
    api.credentials()
    assert login(api, target.email, new_password).status_code == 200


def test_password_is_never_returned(api, db):
    auth_as(api, make_user(Role.ADMINISTRATOR))
    assert all('password' not in u for u in api.get('/api/v1/admin/users/').json()['results'])


def test_createsuperuser_gets_administrator_role(db):
    user = User.objects.create_superuser('root@au.edu.pk', PASSWORD, full_name='Root')
    assert user.role == Role.ADMINISTRATOR and user.is_staff
