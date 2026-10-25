"""The approval chain itself (workflow.perform). The role screens' APIs are tested with each role."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditLog
from apps.workflow.engine import WorkflowError

from .models import Application, StatusChange
from .test_review import cs, cycle, ee, make_complete, make_user, officer, submitted_application, temp_media  # noqa: F401
from .workflow import CHAIN, available_actions, perform


@pytest.fixture
def people(cs, ee):
    return {
        'placement': make_user('po@au.edu.pk', role=Role.PLACEMENT_OFFICER, name='Sana Placement'),
        'admin': make_user('admin@au.edu.pk', role=Role.ADMINISTRATOR, name='Admin'),
        'dac_cs': make_user('dac.cs@au.edu.pk', role=Role.DAC_MEMBER, dept=cs, name='Dr Cs'),
        'dac_cs2': make_user('dac.cs2@au.edu.pk', role=Role.DAC_MEMBER, dept=cs, name='Dr Cs Two'),
        'dac_ee': make_user('dac.ee@au.edu.pk', role=Role.DAC_MEMBER, dept=ee, name='Dr Ee'),
        'director': make_user('director@au.edu.pk', role=Role.DIRECTOR, name='Director'),
        'registrar': make_user('registrar@au.edu.pk', role=Role.REGISTRAR, name='Registrar'),
        'vc': make_user('vc@au.edu.pk', role=Role.VICE_CHANCELLOR, name='VC'),
        'finance': make_user('finance@au.edu.pk', role=Role.FINANCE_OFFICER, name='Finance'),
    }


@pytest.fixture
def case(cycle, cs, officer):
    """A complete CS application at Placement verification."""
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    make_complete(student_api, officer, app_id)
    return app_id


def stage(app_id):
    return Application.objects.get(pk=app_id).status


def forbidden(app_id, action, user, **data):
    with pytest.raises(WorkflowError) as exc:
        perform(app_id, action, user, **data)
    return exc.value.code


def to_director(app_id, people):
    perform(app_id, 'verify', people['placement'])
    perform(app_id, 'shortlist', people['dac_cs'], percentage=60, remarks='Interviewed, genuine need.')
    perform(app_id, 'forward', people['placement'])


def test_the_whole_chain_with_the_percentage_changed_on_the_way(case, people):
    to_director(case, people)
    perform(case, 'approve', people['director'], percentage=50, remarks='Half is enough.')
    perform(case, 'approve', people['registrar'])
    app = perform(case, 'approve', people['vc'], remarks='Approved.')
    assert app.status == 'awaiting_fee_adjustment' and app.scholarship_percentage == 50

    history = list(StatusChange.objects.filter(application_id=case).values_list(
        'action', 'to_status', 'role', 'percentage'))
    assert history == [
        ('submit', 'placement_verification', 'student', None),
        ('verify', 'dac_review', 'placement_officer', None),
        ('shortlist', 'awaiting_forwarding', 'dac_member', 60),
        ('forward', 'director_review', 'placement_officer', None),
        ('approve', 'registrar_review', 'director', 50),
        ('approve', 'vc_review', 'registrar', None),
        ('approve', 'awaiting_fee_adjustment', 'vice_chancellor', None),
    ]
    assert app.reviewed_by == people['vc'] and app.review_remarks == 'Approved.'


@pytest.mark.parametrize('who', ['dac_cs', 'director', 'registrar', 'vc', 'finance'])
def test_only_placement_can_verify(case, people, who):
    assert forbidden(case, 'verify', people[who]) == 'forbidden'


def test_dac_acts_only_for_its_own_department_and_any_member_can(case, people):
    perform(case, 'verify', people['placement'])
    assert forbidden(case, 'shortlist', people['dac_ee'], percentage=50) == 'forbidden'
    assert forbidden(case, 'shortlist', people['placement'], percentage=50) == 'forbidden'
    perform(case, 'shortlist', people['dac_cs2'], percentage=50)
    assert stage(case) == 'awaiting_forwarding'


def test_administrator_takes_placement_actions_only(case, people):
    perform(case, 'verify', people['admin'])
    assert forbidden(case, 'shortlist', people['admin'], percentage=50) == 'forbidden'
    perform(case, 'shortlist', people['dac_cs'], percentage=50)
    perform(case, 'forward', people['admin'])
    assert forbidden(case, 'approve', people['admin']) == 'forbidden'


def test_approvers_act_only_at_their_own_stage(case, people):
    to_director(case, people)
    for at_stage, who, others in [('director_review', 'director', ['registrar', 'vc', 'placement']),
                                  ('registrar_review', 'registrar', ['director', 'vc']),
                                  ('vc_review', 'vc', ['director', 'registrar'])]:
        assert stage(case) == at_stage
        for other in others:
            assert forbidden(case, 'approve', people[other]) == 'forbidden'
        perform(case, 'approve', people[who])


def test_no_skipping_or_repeating(case, people):
    assert forbidden(case, 'forward', people['placement']) == 'stage_conflict'
    perform(case, 'verify', people['placement'])
    assert forbidden(case, 'verify', people['placement']) == 'stage_conflict'  # a second click, or a colleague


def test_shortlist_needs_a_whole_percentage_from_1_to_100(case, people):
    perform(case, 'verify', people['placement'])
    for bad in (None, 0, 101, True):
        with pytest.raises(ValidationError) as exc:
            perform(case, 'shortlist', people['dac_cs'], percentage=bad)
        assert 'percentage' in exc.value.detail
    assert stage(case) == 'dac_review'


def test_percentage_only_where_the_chain_takes_one(case, people):
    with pytest.raises(ValidationError) as exc:
        perform(case, 'verify', people['placement'], percentage=40)
    assert 'percentage' in exc.value.detail


def test_approval_keeps_the_percentage_when_none_is_given(case, people):
    to_director(case, people)
    assert perform(case, 'approve', people['director']).scholarship_percentage == 60


@pytest.mark.parametrize('who,action', [('placement', 'reject'), ('dac_cs', 'not_shortlisted'),
                                        ('director', 'reject')])
def test_rejection_needs_remarks_and_ends_the_case(case, people, who, action):
    if who != 'placement':
        perform(case, 'verify', people['placement'])
    if who == 'director':
        perform(case, 'shortlist', people['dac_cs'], percentage=50)
        perform(case, 'forward', people['placement'])
    with pytest.raises(ValidationError):
        perform(case, action, people[who], remarks='  ')
    perform(case, action, people[who], remarks='Not eligible.')
    assert stage(case) == 'rejected' and CHAIN.is_final('rejected')
    last = StatusChange.objects.filter(application_id=case).last()
    assert last.remarks == 'Not eligible.' and last.to_status == 'rejected'
    assert available_actions(people[who], Application.objects.get(pk=case)) == []


def test_return_needs_remarks_and_only_the_owner_resubmits(case, people, cs):
    with pytest.raises(ValidationError):
        perform(case, 'return', people['placement'])
    perform(case, 'return', people['placement'], remarks='Bank statement is unreadable.')
    assert stage(case) == 'returned'
    other = make_user('other@gmail.com', dept=cs)
    assert forbidden(case, 'resubmit', other) == 'forbidden'
    owner = Application.objects.get(pk=case).student
    perform(case, 'resubmit', owner)
    assert stage(case) == 'placement_verification'


def test_every_action_is_in_the_audit_log(case, people):
    perform(case, 'verify', people['placement'], remarks='Checked.')
    entry = AuditLog.objects.filter(action=AuditAction.WORKFLOW_ACTION, details__action='verify').get()
    assert entry.actor == people['placement'] and entry.actor_role == 'placement_officer'
    assert (entry.target_type, entry.target_id) == ('scholarships.application', str(case))
    assert entry.details['from_status'] == 'placement_verification' and entry.details['to_status'] == 'dac_review'


def test_available_actions_per_person(case, people):
    app = Application.objects.get(pk=case)
    assert [a['action'] for a in available_actions(people['placement'], app)] == ['verify', 'return', 'reject']
    assert available_actions(people['dac_cs'], app) == []
    perform(case, 'verify', people['placement'])
    app.refresh_from_db()
    shortlist = available_actions(people['dac_cs'], app)[0]
    assert shortlist == {'action': 'shortlist', 'label': 'Shortlist', 'to_status': 'awaiting_forwarding',
                         'remarks_required': False, 'percentage': 'required'}
    assert available_actions(people['dac_ee'], app) == []


# ---------- converting Phase 2 statuses ----------

@pytest.mark.django_db(transaction=True)
def test_migration_converts_old_statuses_to_stages():
    executor = MigrationExecutor(connection)
    executor.migrate([('scholarships', '0004_status_history')])
    old = executor.loader.project_state([('scholarships', '0004_status_history')]).apps
    User = old.get_model('accounts', 'User')
    Cycle = old.get_model('scholarships', 'ScholarshipCycle')
    App = old.get_model('scholarships', 'Application')
    Change = old.get_model('scholarships', 'StatusChange')
    cycle = Cycle.objects.create(name='Fall-26', opens_on='2026-10-01', closes_on='2026-11-01')
    officer = User.objects.create(email='po@au.edu.pk', full_name='PO', role='placement_officer')
    made = {}
    for i, status in enumerate(['draft', 'pending', 'under_review', 'approved', 'rejected']):
        student = User.objects.create(email=f's{i}@gmail.com', full_name='S', role='student')
        made[status] = App.objects.create(cycle=cycle, student=student, status=status).pk
        if status != 'draft':
            Change.objects.create(application_id=made[status], from_status='draft', to_status='pending',
                                  changed_by=student)
    Change.objects.create(application_id=made['approved'], from_status='pending', to_status='approved',
                          changed_by=officer)

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())

    stages = dict(Application.objects.values_list('pk', 'status'))
    assert [stages[made[s]] for s in ['draft', 'pending', 'under_review', 'approved', 'rejected']] == [
        'draft', 'placement_verification', 'placement_verification', 'dac_review', 'rejected']
    rows = list(StatusChange.objects.filter(application_id=made['approved']).values_list(
        'from_status', 'to_status', 'action', 'role'))
    assert rows == [('draft', 'placement_verification', 'submit', 'student'),
                    ('placement_verification', 'dac_review', 'status_change', 'placement_officer')]
