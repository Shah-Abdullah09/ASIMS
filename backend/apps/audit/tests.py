import pytest
from django.test import RequestFactory

from apps.accounts.models import Role, User

from .log import record
from .models import AuditAction, AuditLog


@pytest.fixture
def officer(db):
    return User.objects.create_user(email='placement@au.edu.pk', password='x', full_name='Sana Placement',
                                    role=Role.PLACEMENT_OFFICER)


def request_from(user, ip='10.1.2.3'):
    request = RequestFactory().post('/', REMOTE_ADDR=ip)
    request.user = user
    return request


def test_record_takes_actor_role_target_and_ip_from_the_request(officer):
    entry = record(AuditAction.ORIGINAL_RECEIVED, request=request_from(officer), target=officer, note='x')
    assert entry.actor == officer and entry.actor_role == 'placement_officer'
    assert (entry.target_type, entry.target_id) == ('accounts.user', str(officer.pk))
    assert entry.details == {'note': 'x'} and entry.ip_address == '10.1.2.3'


def test_record_without_a_user(db):
    from django.contrib.auth.models import AnonymousUser
    entry = record(AuditAction.LOGIN_FAILED, request=request_from(AnonymousUser()), email='who@x.com')
    assert entry.actor is None and entry.actor_role == '' and entry.details == {'email': 'who@x.com'}


def test_entries_cannot_be_changed_or_deleted(officer):
    entry = record(AuditAction.LOGIN, actor=officer)
    entry.details = {'forged': True}
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()
    with pytest.raises(PermissionError):
        AuditLog.objects.update(action=AuditAction.REGISTER)
    with pytest.raises(PermissionError):
        AuditLog.objects.all().delete()
    assert AuditLog.objects.get().details == {}


def test_admin_is_read_only(officer, client):
    admin = User.objects.create_superuser(email='admin@au.edu.pk', password='x', full_name='Admin')
    record(AuditAction.LOGIN, actor=officer)
    client.force_login(admin)
    assert client.get('/admin/audit/auditlog/').status_code == 200
    assert client.get('/admin/audit/auditlog/add/').status_code == 403
    entry = AuditLog.objects.get()
    assert client.post(f'/admin/audit/auditlog/{entry.pk}/delete/', {'post': 'yes'}).status_code == 403
