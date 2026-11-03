"""The Administrator's in-app management APIs: users, cycles and the audit log."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User
from apps.scholarships.models import Application, ScholarshipCycle

from .log import record
from .models import AuditAction, AuditLog


def make(email, role=Role.STUDENT, **extra):
    return User.objects.create_user(email=email, password='x', full_name=extra.pop('name', 'Ali Khan'), role=role,
                                    is_email_verified=True, **extra)


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def admin(db):
    return as_user(make('admin@au.edu.pk', Role.ADMINISTRATOR, name='Admin'))


def emails(response):
    return [u['email'] for u in response.json()['results']]


def test_user_search_and_filters(admin):
    cs = Department.objects.create(name='Computer Science', code='CS')
    make('sana@au.edu.pk', Role.PLACEMENT_OFFICER, name='Sana Placement')
    make('dac@au.edu.pk', Role.DAC_MEMBER, department=cs, name='Dr Kamran')
    make('ali@gmail.com', registration_id='233585')
    make('old@au.edu.pk', Role.DIRECTOR, is_active=False)
    assert emails(admin.get('/api/v1/admin/users/?search=sana')) == ['sana@au.edu.pk']
    assert emails(admin.get('/api/v1/admin/users/?search=233585')) == ['ali@gmail.com']
    assert emails(admin.get('/api/v1/admin/users/?role=dac_member')) == ['dac@au.edu.pk']
    assert emails(admin.get(f'/api/v1/admin/users/?department={cs.pk}')) == ['dac@au.edu.pk']
    assert emails(admin.get('/api/v1/admin/users/?active=false')) == ['old@au.edu.pk']


def test_cycles_create_update_and_delete_rules(admin):
    url = '/api/v1/admin/cycles/'
    created = admin.post(url, {'name': 'Spring-27', 'opens_on': '2027-02-01', 'closes_on': '2027-03-01'},
                         format='json')
    assert created.status_code == 201 and created.json()['is_active'] is True and created.json()['applications'] == 0
    cycle_id = created.json()['id']
    bad = admin.patch(f'{url}{cycle_id}/', {'closes_on': '2027-01-01'}, format='json')
    assert bad.status_code == 400 and 'closes_on' in bad.json()
    assert admin.patch(f'{url}{cycle_id}/', {'is_active': False}, format='json').json()['is_active'] is False
    assert admin.post(url, {'name': 'Spring-27', 'opens_on': '2027-02-01', 'closes_on': '2027-03-01'},
                      format='json').status_code == 400  # names are unique
    used = ScholarshipCycle.objects.get(pk=cycle_id)
    Application.objects.create(cycle=used, student=make('s@gmail.com'))
    assert admin.delete(f'{url}{cycle_id}/').status_code == 400
    empty = ScholarshipCycle.objects.create(name='Unused', opens_on='2027-01-01', closes_on='2027-01-02')
    assert admin.delete(f'{url}{empty.pk}/').status_code == 204
    changes = [e.details['change'] for e in AuditLog.objects.filter(action=AuditAction.CYCLE_CHANGED).order_by('pk')]
    assert changes == ['created', 'updated', 'deleted']


def test_audit_log_browse_and_filter(admin):
    sana = make('sana@au.edu.pk', Role.PLACEMENT_OFFICER, name='Sana Placement')
    record(AuditAction.LOGIN, actor=sana, target=sana)
    record(AuditAction.LOGIN_FAILED, email='nobody@x.com')
    data = admin.get('/api/v1/admin/audit-log/').json()
    assert data['count'] == 2 and data['results'][0]['action'] == 'login_failed'
    assert data['results'][1]['actor'] == 'sana@au.edu.pk' and data['results'][1]['action_label'] == 'Logged in'
    assert admin.get('/api/v1/admin/audit-log/?action=login').json()['count'] == 1
    assert admin.get('/api/v1/admin/audit-log/?actor=placement').json()['count'] == 1
    assert admin.get('/api/v1/admin/audit-log/?date_from=2099-01-01').json()['count'] == 0
    assert admin.get(f'/api/v1/admin/audit-log/?target_type=accounts.user&target_id={sana.pk}').json()['count'] == 1
    actions = admin.get('/api/v1/admin/audit-log/actions/').json()
    assert {'value': 'login', 'label': 'Logged in'} in actions


@pytest.mark.parametrize('role', [Role.PLACEMENT_OFFICER, Role.STUDENT, Role.DIRECTOR])
def test_only_the_administrator(db, role):
    client = as_user(make(f'{role}@au.edu.pk', role))
    for url in ['/api/v1/admin/audit-log/', '/api/v1/admin/cycles/', '/api/v1/admin/users/']:
        assert client.get(url).status_code == 403
