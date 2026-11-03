"""In-app notifications, the email copy and the email switch."""
import importlib

import pytest
from django.core import mail
from rest_framework.test import APIClient

import config.settings as settings_module
from apps.accounts.models import Role, User

from .models import Notification
from .service import notify

URL = '/api/v1/notifications/'


def make(email, **extra):
    return User.objects.create_user(email=email, password='x', full_name='Ali Khan', role=Role.STUDENT,
                                    is_email_verified=True, **extra)


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_notify_in_app_and_by_email_after_commit(db, django_capture_on_commit_callbacks):
    ali, quiet = make('ali@gmail.com'), make('quiet@gmail.com', email_notifications=False)
    gone = make('gone@gmail.com', is_active=False)
    with django_capture_on_commit_callbacks(execute=True):
        notify([ali, quiet, gone], 'Case returned', 'Please correct the items.', '/scholarships/7/review')
    assert Notification.objects.filter(recipient=ali).count() == 1
    assert Notification.objects.filter(recipient=quiet).count() == 1  # in-app stays on
    assert not Notification.objects.filter(recipient=gone).exists()
    (message,) = mail.outbox
    assert message.to == ['ali@gmail.com'] and message.subject == 'ASIMS: Case returned'
    assert 'http://localhost:5173/scholarships/7/review' in message.body


def test_no_email_when_not_asked_or_rolled_back(db, django_capture_on_commit_callbacks):
    ali = make('ali@gmail.com')
    with django_capture_on_commit_callbacks(execute=True):
        notify([ali], 'Stage changed', email=False)
    assert mail.outbox == []
    notify([ali], 'Never committed')  # callbacks are not run: as if the transaction rolled back
    assert mail.outbox == []


def test_a_mail_failure_is_logged_not_raised(db, django_capture_on_commit_callbacks, monkeypatch):
    def broken(*args, **kwargs):
        raise ConnectionError('SMTP down')
    monkeypatch.setattr('apps.notifications.service.send_mail', broken)
    with django_capture_on_commit_callbacks(execute=True):
        notify([make('ali@gmail.com')], 'Hello')
    assert Notification.objects.count() == 1


def test_list_unread_count_and_marking_read(db):
    ali, other = make('ali@gmail.com'), make('other@gmail.com')
    first, second = notify([ali], 'First', email=False)[0], notify([ali], 'Second', email=False)[0]
    notify([other], 'Not yours', email=False)
    api = as_user(ali)
    data = api.get(URL).json()
    assert data['unread'] == 2 and [n['title'] for n in data['results']] == ['Second', 'First']
    assert api.post(f'{URL}{first.pk}/read/').json()['read_at']
    assert api.get(f'{URL}?unread=true').json()['count'] == 1
    assert api.post(f'{URL}read-all/').json() == {'marked_read': 1}
    assert api.get(URL).json()['unread'] == 0
    assert api.post(f"{URL}{Notification.objects.get(recipient=other).pk}/read/").status_code == 404
    assert second.pk and APIClient().get(URL).status_code == 401


def test_the_email_switch_is_on_the_profile(db):
    api = as_user(make('ali@gmail.com'))
    assert api.get('/api/v1/auth/me/').json()['email_notifications'] is True
    assert api.patch('/api/v1/auth/me/', {'email_notifications': False}, format='json').json()[
        'email_notifications'] is False
    assert User.objects.get().email_notifications is False


@pytest.mark.parametrize('host,backend', [('', 'console'), ('smtp.example.com', 'smtp')])
def test_email_backend_follows_the_mail_server_setting(monkeypatch, host, backend):
    monkeypatch.setenv('EMAIL_HOST', host)
    monkeypatch.delenv('EMAIL_BACKEND', raising=False)
    reloaded = importlib.reload(settings_module)
    assert reloaded.EMAIL_BACKEND == f'django.core.mail.backends.{backend}.EmailBackend'
    monkeypatch.undo()
    importlib.reload(settings_module)
