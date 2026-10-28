"""Change password, forgot password and the Administrator's set-password invitation."""
import re
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.audit.models import AuditAction, AuditLog

from . import passwords
from .models import Role, User

PASSWORD = 'Str0ng-Passw0rd!'
NEW = 'An0ther-Str0ng-One!'


def make(email='ali@gmail.com', role=Role.STUDENT, **extra):
    extra.setdefault('is_email_verified', True)
    return User.objects.create_user(email=email, password=PASSWORD, full_name='Ali Khan', role=role, **extra)


def login(email, password):
    return APIClient().post('/api/v1/auth/login/', {'email': email, 'password': password}, format='json')


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def token_from(message):
    return re.search(r'reset-password\?token=(\S+)', message.body).group(1)


def reset(token, password=NEW):
    return APIClient().post('/api/v1/auth/password/reset/', {'token': token, 'new_password': password}, format='json')


def forgot(email, client=None):
    return (client or APIClient()).post('/api/v1/auth/password/forgot/', {'email': email}, format='json')


# ---------- change password (logged in) ----------

def test_change_password(db):
    ali = make()
    url = '/api/v1/auth/password/change/'
    api = as_user(ali)
    assert api.post(url, {'current_password': 'wrong', 'new_password': NEW}, format='json').json() == {
        'current_password': ['Your current password is not correct.']}
    assert 'new_password' in api.post(url, {'current_password': PASSWORD, 'new_password': '12345678'},
                                      format='json').json()  # too common and all numbers
    assert 'new_password' in api.post(url, {'current_password': PASSWORD, 'new_password': PASSWORD},
                                      format='json').json()
    assert api.post(url, {'current_password': PASSWORD, 'new_password': NEW}, format='json').status_code == 200
    assert login('ali@gmail.com', PASSWORD).status_code == 401
    assert login('ali@gmail.com', NEW).status_code == 200
    assert AuditLog.objects.filter(action=AuditAction.PASSWORD_CHANGED, actor=ali).count() == 1


def test_change_password_needs_login(db):
    assert APIClient().post('/api/v1/auth/password/change/', {}, format='json').status_code == 401


# ---------- forgot password ----------

def test_forgot_replies_the_same_for_unknown_emails_and_sends_nothing(db):
    make()
    known, unknown = forgot('ali@gmail.com'), forgot('nobody@gmail.com')
    assert known.status_code == unknown.status_code == 200 and known.json() == unknown.json()
    (message,) = mail.outbox
    assert message.to == ['ali@gmail.com'] and 'Reset your ASIMS password' in message.subject
    assert 'expires in 1 hour' in message.body
    found = {e.details['email']: e.details['account_found'] for e in
             AuditLog.objects.filter(action=AuditAction.PASSWORD_RESET_REQUESTED)}
    assert found == {'ali@gmail.com': True, 'nobody@gmail.com': False}


def test_forgot_is_rate_limited(db):
    client = APIClient()
    assert [forgot('x@gmail.com', client).status_code for _ in range(6)] == [200] * 5 + [429]


def test_reset_link_sets_the_password_once(db):
    make()
    forgot('ali@gmail.com')
    token = token_from(mail.outbox[0])
    weak = reset(token, 'password')
    assert weak.status_code == 400 and 'new_password' in weak.json()
    assert reset(token).status_code == 200  # the weak attempt did not use the link up
    assert login('ali@gmail.com', NEW).status_code == 200
    again = reset(token, 'Yet-An0ther-0ne!')
    assert again.status_code == 400 and 'already been used' in again.json()['detail']
    entry = AuditLog.objects.get(action=AuditAction.PASSWORD_SET_FROM_LINK)
    assert entry.details == {'link': 'reset'}


def test_forged_expired_or_inactive_links_are_refused(db, monkeypatch):
    ali = make()
    token = passwords.make_password_token(ali, passwords.RESET)
    assert reset(token[:-2] + 'xx').status_code == 400
    monkeypatch.setitem(passwords.LIFETIME, passwords.RESET, -1)
    assert reset(token).status_code == 400
    monkeypatch.setitem(passwords.LIFETIME, passwords.RESET, 3600)
    User.objects.filter(pk=ali.pk).update(is_active=False)
    assert reset(token).status_code == 400


def test_a_reset_link_also_confirms_the_email(db):
    make(is_email_verified=False)
    forgot('ali@gmail.com')
    reset(token_from(mail.outbox[0]))
    assert User.objects.get().is_email_verified and login('ali@gmail.com', NEW).status_code == 200


def test_no_password_is_ever_written_to_the_audit_log(db):
    ali = make()
    as_user(ali).post('/api/v1/auth/password/change/', {'current_password': PASSWORD, 'new_password': NEW},
                      format='json')
    forgot('ali@gmail.com')
    reset(token_from(mail.outbox[0]), 'Th1rd-Passw0rd!')
    text = str(list(AuditLog.objects.values_list('details', flat=True)))
    assert PASSWORD not in text and NEW not in text and 'Th1rd' not in text


# ---------- staff invitation ----------

@pytest.fixture
def admin_api(db):
    return as_user(make('admin@au.edu.pk', role=Role.ADMINISTRATOR))


def test_account_without_a_password_gets_an_invitation(admin_api):
    created = admin_api.post('/api/v1/admin/users/', {'email': 'po@au.edu.pk', 'full_name': 'Sana Placement',
                                                      'role': 'placement_officer'}, format='json')
    assert created.status_code == 201
    (message,) = mail.outbox
    assert message.to == ['po@au.edu.pk'] and 'set your password' in message.subject
    assert 'Placement Officer' in message.body and 'expires in 72 hours' in message.body
    assert login('po@au.edu.pk', '').status_code in (400, 401)
    assert reset(token_from(message)).status_code == 200
    assert login('po@au.edu.pk', NEW).status_code == 200
    assert AuditLog.objects.filter(action=AuditAction.INVITATION_SENT).count() == 1
    assert AuditLog.objects.get(action=AuditAction.PASSWORD_SET_FROM_LINK).details == {'link': 'invite'}


def test_account_with_a_password_gets_no_invitation_and_invites_can_be_resent(admin_api):
    created = admin_api.post('/api/v1/admin/users/', {'email': 'po@au.edu.pk', 'full_name': 'Sana',
                                                      'role': 'placement_officer', 'password': PASSWORD},
                             format='json').json()
    assert mail.outbox == []
    response = admin_api.post(f"/api/v1/admin/users/{created['id']}/invite/")
    assert response.status_code == 200 and response.json()['detail'] == 'Invitation sent to po@au.edu.pk.'
    assert len(mail.outbox) == 1
    student = as_user(make('s@gmail.com'))
    assert student.post(f"/api/v1/admin/users/{created['id']}/invite/").status_code == 403


def test_django_admin_action_sends_invitations(db, client):
    staff = make('po@au.edu.pk', role=Role.PLACEMENT_OFFICER)
    client.force_login(User.objects.create_superuser(email='root@au.edu.pk', password=PASSWORD, full_name='Root'))
    client.post('/admin/accounts/user/', {'action': 'send_invitation', '_selected_action': [staff.pk]})
    assert [m.to for m in mail.outbox] == [['po@au.edu.pk']]


# ---------- testing helper ----------

def test_password_link_command_prints_a_working_link(db):
    make()
    out = StringIO()
    call_command('password_link', 'ali@gmail.com', stdout=out)
    token = re.search(r'token=(\S+)', out.getvalue()).group(1)
    assert reset(token).status_code == 200
