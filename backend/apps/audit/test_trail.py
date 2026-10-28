"""The audit trail across the system (Phase 3 step 5): who did what, recorded where it happens."""
from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User
from apps.accounts.views import make_verification_token
from apps.scholarships.models import Application, ScholarshipCycle
from apps.scholarships.test_submission import FATHER, MOTHER, pdf

from .models import AuditAction, AuditLog

PASSWORD = 'Str0ng-Passw0rd!'
A = AuditAction


@pytest.fixture(autouse=True)
def temp_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def cs(db):
    return Department.objects.create(name='Computer Science', code='CS')


def user(email, role=Role.STUDENT, dept=None, **extra):
    return User.objects.create_user(email=email, password=PASSWORD, full_name='Ali Khan', role=role, department=dept,
                                    is_email_verified=True, **extra)


def as_user(u):
    client = APIClient(REMOTE_ADDR='10.0.0.7')
    client.force_authenticate(u)
    return client


def entries(action):
    return list(AuditLog.objects.filter(action=action).order_by('pk'))


def login(email, password=PASSWORD):
    return APIClient(REMOTE_ADDR='10.0.0.9').post('/api/v1/auth/login/', {'email': email, 'password': password},
                                                  format='json')


# ---------- accounts ----------

def test_registration_and_verification(cs):
    api = APIClient(REMOTE_ADDR='10.0.0.5')
    api.post('/api/v1/auth/register/', {'email': 'ali@gmail.com', 'full_name': 'Ali Khan', 'password': PASSWORD,
                                        'department': cs.pk}, format='json')
    (reg,) = entries(A.REGISTER)
    new = User.objects.get(email='ali@gmail.com')
    assert reg.actor == new and reg.ip_address == '10.0.0.5' and reg.details == {'department': cs.pk}
    token = make_verification_token(new)
    api.post('/api/v1/auth/verify-email/', {'token': token}, format='json')
    api.post('/api/v1/auth/verify-email/', {'token': token}, format='json')  # clicking the link twice
    assert len(entries(A.VERIFY_EMAIL)) == 1


def test_logins_and_failures_without_the_password(cs):
    ali = user('ali@gmail.com', dept=cs)
    User.objects.create_user(email='new@gmail.com', password=PASSWORD, full_name='New', department=cs)  # unverified
    assert login('ali@gmail.com').status_code == 200
    assert login('ali@gmail.com', 'wrong-password').status_code == 401
    assert login('nobody@gmail.com', 'whatever').status_code == 401
    assert login('new@gmail.com').status_code == 401  # not verified yet
    (ok,) = entries(A.LOGIN)
    assert ok.actor == ali and ok.ip_address == '10.0.0.9'
    wrong, unknown, unverified = entries(A.LOGIN_FAILED)
    assert wrong.actor == ali and wrong.details['email'] == 'ali@gmail.com'
    assert unknown.actor is None and unknown.details['email'] == 'nobody@gmail.com'
    assert 'verify your email' in unverified.details['reason']
    assert not AuditLog.objects.filter(details__icontains='wrong-password').exists()
    assert all('password' not in str(e.details) for e in AuditLog.objects.all())


def test_profile_change(cs):
    ali = user('ali@gmail.com', dept=cs)
    as_user(ali).patch('/api/v1/auth/me/', {'registration_id': '233585'}, format='json')
    (entry,) = entries(A.USER_UPDATED)
    assert entry.actor == ali and entry.details == {'fields': ['registration_id']}


def test_administrator_account_and_department_changes(cs):
    admin = as_user(user('admin@au.edu.pk', role=Role.ADMINISTRATOR))
    created = admin.post('/api/v1/admin/users/', {'email': 'po@au.edu.pk', 'full_name': 'Sana', 'role': 'placement_officer',
                                                  'password': PASSWORD}, format='json').json()
    admin.patch(f"/api/v1/admin/users/{created['id']}/", {'is_active': False, 'password': 'An0ther-Passw0rd!'},
                format='json')
    (made,) = entries(A.USER_CREATED)
    assert made.details['role'] == 'placement_officer' and made.details['password'] == 'set'
    (changed,) = entries(A.USER_UPDATED)
    assert changed.details == {'is_active': False, 'password': 'set'}
    assert PASSWORD not in str(made.details) and 'An0ther' not in str(changed.details)

    dept = admin.post('/api/v1/admin/departments/', {'name': 'Software Engineering', 'code': 'SE'}, format='json').json()
    admin.patch(f"/api/v1/admin/departments/{dept['id']}/", {'is_active': False}, format='json')
    assert [(e.details['change'], e.details['code']) for e in entries(A.DEPARTMENT_CHANGED)] == [
        ('created', 'SE'), ('updated', 'SE')]


# ---------- scholarship application ----------

def test_application_work_is_recorded(cs):
    today = timezone.localdate()
    cycle = ScholarshipCycle.objects.create(name='Fall-26', opens_on=today - timedelta(days=1),
                                            closes_on=today + timedelta(days=30))
    ali = user('ali@gmail.com', dept=cs)
    api = as_user(ali)
    base = '/api/v1/scholarships/applications/'
    app_id = api.post(base, {'cycle': cycle.pk}, format='json').json()['id']
    api.patch(f'{base}{app_id}/sections/parents/', {'parents': [FATHER, MOTHER]}, format='json')
    doc_id = api.post(f'{base}{app_id}/documents/', {'slot': 'domicile', 'file': pdf('dom.pdf')},
                      format='multipart').json()['id']
    api.put(f'{base}{app_id}/documents/{doc_id}/', {'file': pdf('dom2.pdf')}, format='multipart')
    api.delete(f'{base}{app_id}/documents/{doc_id}/')
    decl_id = api.get(f'{base}{app_id}/declarations/').json()[0]['id']
    api.post(f'{base}{app_id}/declarations/{decl_id}/scan/', {'file': pdf('stamp.pdf')}, format='multipart')
    Application.objects.filter(pk=app_id).update(status='placement_verification')
    officer = as_user(user('po@au.edu.pk', role=Role.PLACEMENT_OFFICER))
    officer.post(f'/api/v1/scholarships/declarations/{decl_id}/receive/', {}, format='json')
    officer.delete(f'/api/v1/scholarships/declarations/{decl_id}/receive/')

    trail = [(e.action, e.actor.email) for e in AuditLog.objects.order_by('pk')]
    assert trail == [
        (A.APPLICATION_CREATED, 'ali@gmail.com'), (A.APPLICATION_SAVED, 'ali@gmail.com'),
        (A.DOCUMENT_UPLOADED, 'ali@gmail.com'), (A.DOCUMENT_REPLACED, 'ali@gmail.com'),
        (A.DOCUMENT_DELETED, 'ali@gmail.com'), (A.SCAN_UPLOADED, 'ali@gmail.com'),
        (A.ORIGINAL_RECEIVED, 'po@au.edu.pk'), (A.ORIGINAL_UNRECEIVED, 'po@au.edu.pk')]
    saved = entries(A.APPLICATION_SAVED)[0]
    assert saved.details == {'section': 'parents', 'fields': ['parents'], 'stage': 'draft'}
    replaced = entries(A.DOCUMENT_REPLACED)[0]
    assert replaced.details['replaced'] == 'dom.pdf' and replaced.details['name'] == 'dom2.pdf'
    assert all(e.ip_address == '10.0.0.7' for e in AuditLog.objects.all())


# ---------- Django admin cannot bypass the chain ----------

def test_admin_shows_but_cannot_change_the_stage(cs, client):
    cycle = ScholarshipCycle.objects.create(name='Fall-26', opens_on=date(2026, 10, 1), closes_on=date(2026, 11, 1))
    app = Application.objects.create(cycle=cycle, student=user('ali@gmail.com', dept=cs), status='dac_review',
                                     scholarship_percentage=40)
    client.force_login(User.objects.create_superuser(email='root@au.edu.pk', password=PASSWORD, full_name='Root'))
    page = client.get(f'/admin/scholarships/application/{app.pk}/change/').content.decode()
    assert 'DAC review' in page and 'name="status"' not in page and 'name="scholarship_percentage"' not in page
