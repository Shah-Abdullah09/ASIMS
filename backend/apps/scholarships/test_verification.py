"""Placement verification (Phase 3 step 2): file review, section flags, return, resubmit and verify."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditLog

from .models import Application, ApplicationDocument, ScholarshipCycle, SectionFlag
from .test_review import (REVIEW, STUDENT_BASE, act, client_for, cs, cycle, make_complete, make_user,  # noqa: F401
                          officer, ready_for_dac, submitted_application, temp_media, verify_documents)
from .test_submission import pdf


@pytest.fixture
def case(cycle, cs, officer):
    """(student client, application id) for a submitted CS application with Form 2 complete."""
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    make_complete(student_api, officer, app_id)
    return student_api, app_id


def detail(client, app_id):
    return client.get(f'{REVIEW}{app_id}/').json()


def files(client, app_id, slot):
    return next(d for d in detail(client, app_id)['documents'] if d['slot'] == slot)['files']


def review(client, app_id, doc_id, review_status, note=''):
    return client.post(f'{REVIEW}{app_id}/documents/{doc_id}/review/', {'review_status': review_status, 'note': note},
                       format='json')


def flag(client, app_id, section, note='Please correct this.'):
    return client.post(f'{REVIEW}{app_id}/flags/', {'section': section, 'note': note}, format='json')


def return_with_bank_statement_unclear(student_api, officer, app_id):
    doc_id = files(officer, app_id, 'bank_statements')[0]['id']
    review(officer, app_id, doc_id, 'needs_clarification', 'The statement is cut off at the bottom.')
    flag(officer, app_id, 'accommodation', 'Plot size looks wrong.')
    assert act(officer, app_id, 'return', 'Please fix the flagged items.').status_code == 200
    return doc_id


# ---------- reviewing files ----------

def test_files_are_reviewed_one_by_one_and_the_student_sees_the_note(case, officer):
    student_api, app_id = case
    doc = files(officer, app_id, 'domicile')[0]
    assert doc['review_status'] == ''
    response = review(officer, app_id, doc['id'], 'needs_clarification', 'Stamp is not readable.')
    assert response.status_code == 200
    assert response.json()['review_status'] == 'needs_clarification' and response.json()['reviewed_by'] == 'Sana Placement'
    mine = student_api.get(f'{STUDENT_BASE}{app_id}/documents/').json()
    domicile = next(d for d in mine if d['slot'] == 'domicile')['files'][0]
    assert domicile['review_note'] == 'Stamp is not readable.'
    entry = AuditLog.objects.get(action=AuditAction.DOCUMENT_REVIEWED)
    assert entry.details['application'] == app_id and entry.details['review_status'] == 'needs_clarification'


def test_needs_clarification_requires_a_note(case, officer):
    _, app_id = case
    doc_id = files(officer, app_id, 'domicile')[0]['id']
    response = review(officer, app_id, doc_id, 'needs_clarification', '  ')
    assert response.status_code == 400 and 'note' in response.json()
    assert review(officer, app_id, doc_id, 'maybe').status_code == 400


def test_file_of_another_application_is_not_found(case, officer, cycle, cs):
    _, app_id = case
    _, other_id = submitted_application(cycle, cs, 'sara@gmail.com', 'Sara Ahmed', '2335901', '36302-7654321-2')
    other_doc = files(officer, other_id, 'domicile')[0]['id']
    assert review(officer, app_id, other_doc, 'verified').status_code == 404


@pytest.mark.parametrize('role', [Role.STUDENT, Role.DAC_MEMBER, Role.DIRECTOR])
def test_only_placement_reviews(case, officer, cs, role):
    _, app_id = case
    doc_id = files(officer, app_id, 'domicile')[0]['id']
    other = client_for(make_user(f'{role}@au.edu.pk', role=role, dept=cs))
    assert review(other, app_id, doc_id, 'verified').status_code == 403
    assert flag(other, app_id, 'income').status_code == 403


def test_review_and_flags_only_during_placement_verification(case, officer):
    student_api, app_id = case
    doc_id = files(officer, app_id, 'domicile')[0]['id']
    flag(officer, app_id, 'income')
    act(officer, app_id, 'return', 'Fix income.')
    assert review(officer, app_id, doc_id, 'verified').status_code == 409
    assert flag(officer, app_id, 'personal').status_code == 409


# ---------- flags ----------

def test_flagging_twice_updates_the_open_flag_and_clearing_keeps_history(case, officer):
    _, app_id = case
    first = flag(officer, app_id, 'income', 'Net pay missing.').json()
    second = flag(officer, app_id, 'income', 'Net pay and the salary slip disagree.').json()
    assert first['id'] == second['id'] and second['note'] == 'Net pay and the salary slip disagree.'
    assert second['section_label'] == 'Income' and second['is_open']
    cleared = officer.delete(f'{REVIEW}{app_id}/flags/{first["id"]}/')
    assert cleared.status_code == 200 and cleared.json()['resolution'] == 'cleared' and not cleared.json()['is_open']
    assert officer.delete(f'{REVIEW}{app_id}/flags/{first["id"]}/').status_code == 404  # already closed
    assert flag(officer, app_id, 'income', 'Again.').json()['id'] != first['id']
    assert SectionFlag.objects.filter(application_id=app_id).count() == 2
    assert [f['is_open'] for f in detail(officer, app_id)['flags']] == [False, True]


def test_flag_needs_a_known_section_and_a_note(case, officer):
    _, app_id = case
    assert flag(officer, app_id, 'nowhere').status_code == 400
    assert flag(officer, app_id, 'income', '   ').status_code == 400


# ---------- return ----------

def test_return_needs_something_to_fix_and_a_reason(case, officer):
    _, app_id = case
    response = act(officer, app_id, 'return', 'Please fix.')
    assert response.status_code == 400 and 'Flag at least one section' in str(response.json())
    flag(officer, app_id, 'income')
    assert act(officer, app_id, 'return', '').status_code == 400  # reason required
    assert act(officer, app_id, 'return', 'Please fix the income section.').json()['status'] == 'returned'


def test_returned_application_reopens_only_what_was_flagged(case, officer):
    student_api, app_id = case
    unclear = return_with_bank_statement_unclear(student_api, officer, app_id)
    mine = student_api.get(f'{STUDENT_BASE}{app_id}/').json()
    assert mine['status'] == 'returned' and mine['status_label'] == 'Returned to student'
    assert mine['unlocked'] == {'sections': ['accommodation'], 'slots': ['bank_statements']}
    assert [f['section'] for f in mine['flags'] if f['is_open']] == ['accommodation']

    base = f'{STUDENT_BASE}{app_id}'
    assert student_api.patch(f'{base}/sections/accommodation/', {'plot_size_sqft': 1350},
                             format='json').status_code == 200
    locked = student_api.patch(f'{base}/sections/personal/', {'domicile': 'Lahore'}, format='json')
    assert locked.status_code == 403 and 'did not ask for changes' in locked.json()['detail']
    assert student_api.post(f'{base}/documents/', {'slot': 'domicile', 'file': pdf()},
                            format='multipart').status_code == 403

    replaced = student_api.put(f'{base}/documents/{unclear}/', {'file': pdf('clear.pdf')}, format='multipart')
    assert replaced.status_code == 200 and replaced.json()['review_status'] == ''  # to be checked again
    assert student_api.post(f'{base}/documents/', {'slot': 'bank_statements', 'file': pdf()},
                            format='multipart').status_code == 201


def test_verified_files_stay_locked_in_a_reopened_slot(case, officer):
    student_api, app_id = case
    # Two domicile files: one verified, one unclear, so the slot reopens with a verified file in it
    student = Application.objects.get(pk=app_id).student
    extra = ApplicationDocument.objects.create(application_id=app_id, slot='domicile', file='d2.pdf',
                                               original_name='d2.pdf', content_type='application/pdf', size=1,
                                               uploaded_by=student)
    good = files(officer, app_id, 'domicile')[0]['id']
    review(officer, app_id, good, 'verified')
    review(officer, app_id, extra.pk, 'needs_clarification', 'Blurred.')
    act(officer, app_id, 'return', 'Second domicile page is blurred.')
    base = f'{STUDENT_BASE}{app_id}/documents'
    assert student_api.put(f'{base}/{good}/', {'file': pdf()}, format='multipart').status_code == 403
    assert student_api.delete(f'{base}/{good}/').status_code == 403
    assert student_api.put(f'{base}/{extra.pk}/', {'file': pdf()}, format='multipart').status_code == 200


def test_a_changed_answer_that_needs_a_new_document_reopens_that_slot(case, officer):
    student_api, app_id = case
    flag(officer, app_id, 'accommodation', 'You live in a rented house, not your own.')
    act(officer, app_id, 'return', 'Correct the accommodation status.')
    base = f'{STUDENT_BASE}{app_id}'
    student_api.patch(f'{base}/sections/accommodation/', {'accommodation_status': 'rented', 'rent_paid_by': 'self',
                                                         'monthly_rent': 15000}, format='json')
    assert 'rent_agreement' in student_api.get(f'{base}/').json()['unlocked']['slots']
    assert student_api.post(f'{base}/documents/', {'slot': 'rent_agreement', 'file': pdf()},
                            format='multipart').status_code == 201


# ---------- resubmit ----------

def test_resubmit_runs_the_checks_closes_flags_and_goes_back_to_placement(case, officer):
    student_api, app_id = case
    unclear = return_with_bank_statement_unclear(student_api, officer, app_id)
    base = f'{STUDENT_BASE}{app_id}'
    student_api.patch(f'{base}/sections/accommodation/', {'plot_size_sqft': None}, format='json')
    response = student_api.post(f'{base}/resubmit/')
    assert response.status_code == 400 and 'accommodation' in response.json()['sections']

    student_api.patch(f'{base}/sections/accommodation/', {'plot_size_sqft': 1350}, format='json')
    student_api.put(f'{base}/documents/{unclear}/', {'file': pdf('clear.pdf')}, format='multipart')
    response = student_api.post(f'{base}/resubmit/', {'remarks': 'Uploaded the full statement.'}, format='json')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'placement_verification' and data['unlocked'] == {'sections': [], 'slots': []}
    assert all(not f['is_open'] and f['resolution'] == 'resubmitted' for f in data['flags'])
    last = data['status_history'][-1]
    assert (last['action'], last['remarks']) == ('resubmit', 'Uploaded the full statement.')
    assert student_api.patch(f'{base}/sections/accommodation/', {'plot_size_sqft': 1}, format='json').status_code == 403


def test_resubmit_only_when_returned_and_submit_is_not_a_way_around(case, officer):
    student_api, app_id = case
    assert student_api.post(f'{STUDENT_BASE}{app_id}/resubmit/').status_code == 403
    flag(officer, app_id, 'income')
    act(officer, app_id, 'return', 'Fix income.')
    assert student_api.post(f'{STUDENT_BASE}{app_id}/submit/').status_code == 403


def test_resubmit_is_allowed_after_the_cycle_closes(case, officer):
    student_api, app_id = case
    flag(officer, app_id, 'income')
    act(officer, app_id, 'return', 'Fix income.')
    yesterday = timezone.localdate() - timedelta(days=1)
    ScholarshipCycle.objects.update(opens_on=yesterday - timedelta(days=30), closes_on=yesterday)
    assert student_api.post(f'{STUDENT_BASE}{app_id}/resubmit/').status_code == 200


def test_another_student_cannot_resubmit(case, officer, cs):
    _, app_id = case
    flag(officer, app_id, 'income')
    act(officer, app_id, 'return', 'Fix income.')
    stranger = client_for(make_user('stranger@gmail.com', dept=cs))
    assert stranger.post(f'{STUDENT_BASE}{app_id}/resubmit/').status_code == 404


# ---------- verify ----------

def test_verify_lists_everything_still_open(case, officer):
    _, app_id = case
    domicile = files(officer, app_id, 'domicile')[0]['id']
    review(officer, app_id, domicile, 'needs_clarification', 'Blurred.')
    flag(officer, app_id, 'income')
    problems = str(act(officer, app_id, 'verify').json())
    assert '1 document(s) still need clarification' in problems
    assert 'required document(s) not verified yet' in problems
    assert '1 flagged section(s) still open' in problems

    verify_documents(officer, app_id)
    flag_id = detail(officer, app_id)['flags'][0]['id']
    officer.delete(f'{REVIEW}{app_id}/flags/{flag_id}/')
    assert act(officer, app_id, 'verify').json()['status'] == 'dac_review'


def test_verify_still_needs_form2_complete(cycle, cs, officer):
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    verify_documents(officer, app_id)
    assert 'Form 2 scan' in str(act(officer, app_id, 'verify').json())
    ready_for_dac(student_api, officer, app_id)
    assert act(officer, app_id, 'verify').status_code == 200


def test_optional_files_need_not_be_verified_but_must_not_be_unclear(case, officer):
    student_api, app_id = case
    ApplicationDocument.objects.create(application_id=app_id, slot='hostel_proof', file='x.pdf', original_name='x.pdf',
                                       content_type='application/pdf', size=1,
                                       uploaded_by=Application.objects.get(pk=app_id).student)
    for slot in detail(officer, app_id)['documents']:
        if slot['required']:
            for f in slot['files']:
                review(officer, app_id, f['id'], 'verified')
    assert act(officer, app_id, 'verify').status_code == 200


def test_form2_receipts_are_final_after_verification(case, officer):
    student_api, app_id = case
    verify_documents(officer, app_id)
    act(officer, app_id, 'verify')
    decl_id = detail(officer, app_id)['declarations'][0]['id']
    response = officer.delete(f'/api/v1/scholarships/declarations/{decl_id}/receive/')
    assert response.status_code == 400 and 'receipts are final' in str(response.json())
