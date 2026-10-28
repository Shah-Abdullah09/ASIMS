from types import SimpleNamespace

import pytest

from .engine import Transition, Workflow, WorkflowError

STAGES = [('draft', 'Draft'), ('check', 'Checking'), ('done', 'Done'), ('rejected', 'Rejected')]


def user(role, dept=None):
    return SimpleNamespace(role=role, department_id=dept)


def same_dept(u, obj):
    return u.department_id == obj.dept


FLOW = Workflow([
    Transition('submit', 'Submit', 'draft', 'check', ('student',)),
    Transition('approve', 'Approve', 'check', 'done', ('checker',), scope=same_dept),
    Transition('reject', 'Reject', 'check', 'rejected', ('checker', 'boss'), remarks_required=True),
], STAGES)

OBJ = SimpleNamespace(dept=1)


def test_find_returns_the_transition():
    t = FLOW.find(user('checker', 1), OBJ, 'check', 'approve')
    assert (t.source, t.target) == ('check', 'done')


def test_unknown_action():
    with pytest.raises(WorkflowError) as exc:
        FLOW.find(user('checker', 1), OBJ, 'check', 'fly')
    assert exc.value.code == 'unknown_action'


def test_wrong_stage_is_a_conflict_with_the_current_stage_named():
    with pytest.raises(WorkflowError) as exc:
        FLOW.find(user('checker', 1), OBJ, 'done', 'approve')
    assert exc.value.code == 'stage_conflict' and '"Done"' in exc.value.message


def test_wrong_role_and_out_of_scope_are_forbidden():
    for who in (user('student'), user('checker', 2)):
        with pytest.raises(WorkflowError) as exc:
            FLOW.find(who, OBJ, 'check', 'approve')
        assert exc.value.code == 'forbidden'


def test_available_and_acting_roles():
    assert [t.action for t in FLOW.available(user('checker', 1), OBJ, 'check')] == ['approve', 'reject']
    assert [t.action for t in FLOW.available(user('checker', 2), OBJ, 'check')] == ['reject']
    assert [t.action for t in FLOW.available(user('boss'), OBJ, 'check')] == ['reject']
    assert FLOW.acting_roles('check') == {'checker', 'boss'}
    assert FLOW.is_final('done') and not FLOW.is_final('draft')


def test_duplicate_or_unlabelled_transitions_are_refused():
    with pytest.raises(ValueError):
        Workflow([Transition('a', 'A', 'draft', 'check', ()), Transition('a', 'A', 'draft', 'done', ())], STAGES)
    with pytest.raises(ValueError):
        Workflow([Transition('a', 'A', 'draft', 'nowhere', ())], STAGES)
