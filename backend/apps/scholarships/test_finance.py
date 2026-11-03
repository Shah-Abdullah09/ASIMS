"""Finance and award letter (Phase 4)."""
from datetime import date

import pytest
from django.core import mail
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditLog
from apps.workflow.engine import WorkflowError

from .models import Application, AwardLetter, FeeAdjustment, scholarship_amount
from .test_review import act, client_for, cs, cycle, make_user, submitted_application, temp_media  # noqa: F401
from .workflow import CHAIN, available_actions, perform


# ---------- amounts and reference ----------

@pytest.mark.parametrize('fee,pct,amount', [(100000, 60, 60000), (45001, 50, 22501), (99999, 33, 33000),
                                            (150000, 100, 150000), (1, 1, 0)])
def test_scholarship_amount_is_whole_rupees_rounded_half_up(fee, pct, amount):
    assert scholarship_amount(fee, pct) == amount


def test_fee_adjustment_calculates_amount_and_fee_payable():
    adj = FeeAdjustment(semester_fee=145000, percentage=50)
    adj.calculate()
    assert (adj.scholarship_amount, adj.fee_payable) == (72500, 72500)


def test_award_letter_reference(cycle, cs):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    app = Application.objects.select_related('cycle').get(pk=app_id)
    assert AwardLetter.reference_for(app) == f'ASIMS/NBFG/Fall-26/{app_id:04d}'


# ---------- Finance's step in the chain ----------

@pytest.fixture
def approved(cycle, cs):
    """A case the VC has approved at 50%."""
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    Application.objects.filter(pk=app_id).update(status='awaiting_fee_adjustment', scholarship_percentage=50)
    return Application.objects.get(pk=app_id)


@pytest.fixture
def finance(db):
    return make_user('finance@au.edu.pk', role=Role.FINANCE_OFFICER, name='Farah Finance')


def adjust(app, finance, fee=145000):
    adj = FeeAdjustment(application=app, semester_fee=fee, percentage=app.scholarship_percentage,
                        voucher_number='CH-2026-0042', adjusted_on=date(2026, 10, 28), recorded_by=finance)
    adj.calculate()
    adj.save()
    return adj


def test_finance_closes_the_case_once_the_adjustment_is_recorded(approved, finance):
    assert [a['action'] for a in available_actions(finance, approved)] == ['record_fee_adjustment']
    with pytest.raises(ValidationError) as exc:
        perform(approved.pk, 'record_fee_adjustment', finance)
    assert 'fee adjustment details' in str(exc.value.detail)
    adjust(approved, finance)
    app = perform(approved.pk, 'record_fee_adjustment', finance, remarks='Adjusted in the Fall-26 voucher.')
    assert app.status == 'completed' and CHAIN.is_final('completed')
    last = app.status_history.last()
    assert (last.action, last.role, last.to_status) == ('record_fee_adjustment', 'finance_officer', 'completed')


@pytest.mark.parametrize('role', [Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR, Role.VICE_CHANCELLOR, Role.STUDENT])
def test_only_finance_records_the_adjustment(approved, finance, role):
    adjust(approved, finance)
    with pytest.raises(WorkflowError) as exc:
        perform(approved.pk, 'record_fee_adjustment', make_user(f'{role}@au.edu.pk', role=role))
    assert exc.value.code == 'forbidden'


def test_finance_cannot_act_before_the_vc_approves(cycle, cs, finance):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    Application.objects.filter(pk=app_id).update(status='vc_review')
    with pytest.raises(WorkflowError) as exc:
        perform(app_id, 'record_fee_adjustment', finance)
    assert exc.value.code == 'stage_conflict'


# ---------- Finance API ----------

FEE = '/api/v1/scholarships/review/applications/{}/fee-adjustment/'


@pytest.fixture
def vc_approved(cycle, cs, django_capture_on_commit_callbacks):
    """(student client, id) of a CS case the VC approved at 50% through the API (so the letter exists)."""
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    Application.objects.filter(pk=app_id).update(status='vc_review', scholarship_percentage=50)
    vc = client_for(make_user('vc@au.edu.pk', role=Role.VICE_CHANCELLOR))
    with django_capture_on_commit_callbacks(execute=True):
        act(vc, app_id, 'approve')
    return student_api, app_id


@pytest.fixture
def finance_api(finance):
    return client_for(finance)


def record_fee(client, app_id, **over):
    data = {'semester_fee': 145001, 'voucher_number': 'CH-2026-0042',
            'adjusted_on': date.today().isoformat(), 'remarks': '', **over}
    return client.post(FEE.format(app_id), data, format='json')


def test_finance_queue_and_letter(vc_approved, finance_api, cycle, cs):
    _, app_id = vc_approved
    _, other = submitted_application(cycle, cs, 'sara@gmail.com', 'Sara Ahmed', '2335901', '36302-7654321-2')
    Application.objects.filter(pk=other).update(status='vc_review')
    rows = finance_api.get('/api/v1/scholarships/review/applications/').json()['results']
    assert [r['id'] for r in rows] == [app_id]
    assert finance_api.get(f'/api/v1/scholarships/review/applications/{other}/').status_code == 404
    detail = finance_api.get(f'/api/v1/scholarships/review/applications/{app_id}/').json()
    assert detail['available_actions'][0]['action'] == 'record_fee_adjustment' and detail['fee_adjustment'] is None
    assert finance_api.get(f'/api/v1/scholarships/award-letters/{app_id}/').status_code == 200


def test_recording_the_adjustment_completes_the_case(vc_approved, finance_api, django_capture_on_commit_callbacks):
    student_api, app_id = vc_approved
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        response = record_fee(finance_api, app_id, remarks='Adjusted in the Fall-26 voucher.')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'completed' and data['available_actions'] == []
    assert {k: data['fee_adjustment'][k] for k in ('semester_fee', 'percentage', 'scholarship_amount', 'fee_payable')} \
        == {'semester_fee': 145001, 'percentage': 50, 'scholarship_amount': 72501, 'fee_payable': 72500}
    assert data['fee_adjustment']['recorded_by'] == 'Farah Finance'
    assert data['status_history'][-1]['action'] == 'record_fee_adjustment'
    (message,) = mail.outbox
    assert 'Rs 72,501' in message.body and 'Rs 72,500' in message.body and 'CH-2026-0042' in message.body
    entry = AuditLog.objects.get(action=AuditAction.FEE_ADJUSTMENT_RECORDED)
    assert entry.details['scholarship_amount'] == 72501
    mine = student_api.get(f'/api/v1/scholarships/applications/{app_id}/').json()
    assert mine['status'] == 'completed' and mine['fee_adjustment']['fee_payable'] == 72500
    assert mine['scholarship_percentage'] == 50  # still shown once completed
    # Finance still sees it (completed), but it cannot be recorded twice
    again = record_fee(finance_api, app_id)
    assert again.status_code == 409


@pytest.mark.parametrize('field,value', [('semester_fee', 0), ('voucher_number', '  '), ('adjusted_on', '2099-01-01'),
                                         ('adjusted_on', '2020-01-01')])
def test_adjustment_checks(vc_approved, finance_api, field, value):
    _, app_id = vc_approved
    response = record_fee(finance_api, app_id, **{field: value})
    assert response.status_code == 400 and field in response.json()
    assert Application.objects.get(pk=app_id).status == 'awaiting_fee_adjustment'


def test_only_finance_records_the_fee(vc_approved, cs):
    _, app_id = vc_approved
    for role in [Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR]:
        assert record_fee(client_for(make_user(f'{role}.f@au.edu.pk', role=role)), app_id).status_code == 403
    assert record_fee(client_for(make_user('s@gmail.com', dept=cs)), app_id).status_code == 403
