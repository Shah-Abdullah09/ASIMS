"""Finance and award letter (Phase 4)."""
from datetime import date

import pytest
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role
from apps.workflow.engine import WorkflowError

from .models import Application, AwardLetter, FeeAdjustment, scholarship_amount
from .test_review import cs, cycle, make_user, submitted_application, temp_media  # noqa: F401
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
