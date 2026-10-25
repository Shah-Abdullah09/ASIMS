from datetime import timedelta

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User

from .declarations import BLANK, CLOSING
from .models import Application, Declaration, ScholarshipCycle

PASSWORD = 'Str0ng-Passw0rd!'
BASE = '/api/v1/scholarships/applications/'
PDF = b'%PDF-1.4\n%%EOF\n'
ALWAYS_DOCS = ['cnic_copies', 'domicile', 'bank_statements', 'fee_receipts', 'utility_bills', 'result_cards']


@pytest.fixture(autouse=True)
def temp_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def dept(db):
    return Department.objects.create(name='Computer Science', code='CS')


@pytest.fixture
def cycle(db):
    today = timezone.localdate()
    return ScholarshipCycle.objects.create(name='Fall-26', opens_on=today - timedelta(days=1),
                                           closes_on=today + timedelta(days=30))


def make_user(email, role=Role.STUDENT, dept=None, **extra):
    return User.objects.create_user(email=email, password=PASSWORD, full_name='Ali Khan', role=role,
                                    department=dept, is_email_verified=True, **extra)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def student(dept):
    return make_user('ali@gmail.com', dept=dept, registration_id='233585')


@pytest.fixture
def api(student):
    return client_for(student)


@pytest.fixture
def officer(dept):
    return client_for(make_user('placement@au.edu.pk', role=Role.PLACEMENT_OFFICER, dept=dept))


@pytest.fixture
def app_id(api, cycle):
    return api.post(BASE, {'cycle': cycle.pk}, format='json').json()['id']


def save(api, app_id, section, data):
    response = api.patch(f'{BASE}{app_id}/sections/{section}/', data, format='json')
    assert response.status_code == 200, response.json()
    return response.json()


def pdf(name='scan.pdf'):
    return SimpleUploadedFile(name, PDF)


FATHER = {'role': 'father', 'name': 'Muhammad Aslam', 'cnic': '36302-1111111-1', 'status': 'alive',
          'profession': 'employed', 'employer': 'WAPDA Multan', 'occupation_type': 'Government',
          'designation_grade': 'Assistant BPS-15', 'gross_monthly_income': 80000, 'net_monthly_income': 72000}
MOTHER = {'role': 'mother', 'name': 'Bano Bibi', 'cnic': '36302-2222222-2', 'status': 'alive',
          'profession': 'not_earning'}


def fill_complete(api, app_id, parents=None, cnic='36302-1234567-1'):
    """Fill every required answer and upload every always-required document."""
    save(api, app_id, 'personal', {
        'program': 'BS Software Engineering', 'gender': 'male', 'marital_status': 'single',
        'cnic': cnic, 'date_of_birth': '2004-05-01', 'domicile': 'Multan',
        'present_address': 'House 1, Street 2, Multan', 'permanent_address': 'House 1, Street 2, Multan',
        'mobile': '03001234567'})
    save(api, app_id, 'household', {'total_family_members': 3, 'household_members': [
        {'name': 'Muhammad Aslam', 'relationship': 'father'}, {'name': 'Bano Bibi', 'relationship': 'mother'}]})
    save(api, app_id, 'parents', {'parents': parents or [FATHER, MOTHER]})
    save(api, app_id, 'income', {'applicant_gross_income': 0, 'applicant_net_income': 0, 'earning_members': [
        {'name': 'Muhammad Aslam', 'relationship': 'father', 'gross_pay': 80000, 'net_pay': 72000}]})
    save(api, app_id, 'accommodation', {
        'accommodation_type': 'town_house', 'accommodation_status': 'owned', 'plot_size_sqft': 1125,
        'covered_area_sqft': 900, 'accommodation_address': 'House 1, Street 2, Multan', 'bedrooms': '1-2',
        'air_conditioners': 'none', 'other_house_owned': False})
    save(api, app_id, 'expenses', {'medical_monthly': 0, 'misc_monthly': 5000, 'utility_months': [
        {'month_index': i, 'electricity': 6000, 'gas': 1000} for i in (1, 2, 3)]})
    save(api, app_id, 'assets', {'owns_transport': False, 'cattle_count': 0, 'education_loan': False,
                                 'admission_fee_paid_how': 'From family savings.'})
    save(api, app_id, 'education', {
        'last_institution_monthly_fee': 3000, 'other_scholarships': False,
        'statement_of_purpose': 'I am the eldest child and my father is the only earning member. ' * 3,
        'education_records': [
            {'level': 'secondary', 'institute': 'Govt High School Multan', 'from_month': '2018-04-01',
             'to_month': '2020-03-01', 'percentage': '82'},
            {'level': 'intermediate', 'institute': 'Govt College Multan', 'from_month': '2020-09-01',
             'to_month': '2022-06-01', 'percentage': '78'}]})
    save(api, app_id, 'undertaking', {'undertaking_accepted': True, 'undertaking_name': 'ali  khan'})
    for slot in ALWAYS_DOCS + ['salary_certificate', 'salary_slip']:
        assert api.post(f'{BASE}{app_id}/documents/', {'slot': slot, 'file': pdf()},
                        format='multipart').status_code == 201


def declarations(api, app_id):
    return api.get(f'{BASE}{app_id}/declarations/').json()


# ---------- readiness and submit ----------

def test_empty_draft_reports_what_is_missing_per_step(api, app_id):
    result = api.get(f'{BASE}{app_id}/readiness/').json()
    assert result['ready'] is False
    assert set(result['sections']) == {'personal', 'household', 'parents', 'income', 'accommodation', 'expenses',
                                       'assets', 'education', 'undertaking'}
    assert 'cnic' in result['sections']['personal']
    assert 'applicant_name' not in result['sections']['personal']  # prefilled from the account
    assert set(result['missing_documents']) == set(ALWAYS_DOCS)


def test_incomplete_application_cannot_be_submitted(api, app_id):
    response = api.post(f'{BASE}{app_id}/submit/')
    assert response.status_code == 400 and response.json()['ready'] is False
    assert Application.objects.get(pk=app_id).status == 'draft'


def test_complete_application_submits_locks_and_emails(api, app_id, student):
    fill_complete(api, app_id)
    assert api.get(f'{BASE}{app_id}/readiness/').json() == {
        'ready': True, 'sections': {}, 'missing_documents': [], 'problems': []}

    response = api.post(f'{BASE}{app_id}/submit/')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'placement_verification' and data['submitted_at'] and not data['is_editable']
    assert data['completion'] == {'form_submitted': True, 'declarations_required': 1, 'scans_uploaded': False,
                                  'physical_copies_received': False, 'complete': False}

    assert len(mail.outbox) == 1 and mail.outbox[0].to == [student.email]
    assert f'#{app_id}' in mail.outbox[0].subject and 'stamp-paper' in mail.outbox[0].body

    assert api.patch(f'{BASE}{app_id}/sections/personal/', {'domicile': 'X'}, format='json').status_code == 403
    assert api.post(f'{BASE}{app_id}/documents/', {'slot': 'domicile', 'file': pdf()},
                    format='multipart').status_code == 403
    assert api.post(f'{BASE}{app_id}/submit/').status_code == 403  # no second submission


def test_submit_blocked_when_cycle_has_closed(api, app_id, cycle):
    fill_complete(api, app_id)
    ScholarshipCycle.objects.filter(pk=cycle.pk).update(closes_on=timezone.localdate() - timedelta(days=1))
    response = api.post(f'{BASE}{app_id}/submit/')
    assert response.status_code == 400 and 'closed' in response.json()['problems'][0]


def test_undertaking_name_must_match_applicant_name(api, app_id):
    fill_complete(api, app_id)
    save(api, app_id, 'undertaking', {'undertaking_name': 'Someone Else'})
    sections = api.get(f'{BASE}{app_id}/readiness/').json()['sections']
    assert list(sections) == ['undertaking'] and 'undertaking_name' in sections['undertaking']


def test_guardian_required_when_father_is_deceased(api, app_id):
    fill_complete(api, app_id, parents=[{**FATHER, 'status': 'deceased'}, MOTHER])
    sections = api.get(f'{BASE}{app_id}/readiness/').json()['sections']
    assert 'guardian' in sections['parents']


def test_earning_parent_must_be_listed_as_earning_member(api, app_id):
    fill_complete(api, app_id)
    save(api, app_id, 'income', {'earning_members': []})
    errors = api.get(f'{BASE}{app_id}/readiness/').json()['sections']['income']['earning_members']
    assert "father's income must also be listed" in errors[0]


def test_negative_disposable_income_needs_an_explanation(api, app_id):
    fill_complete(api, app_id)
    save(api, app_id, 'expenses', {'misc_monthly': 500000})
    sections = api.get(f'{BASE}{app_id}/readiness/').json()['sections']
    assert 'negative_income_explanation' in sections['expenses']
    save(api, app_id, 'expenses', {'negative_income_explanation': 'Relatives help us with monthly expenses.'})
    assert 'expenses' not in api.get(f'{BASE}{app_id}/readiness/').json()['sections']


# ---------- Form 2 text ----------

def test_one_declaration_per_earning_parent(api, app_id):
    save(api, app_id, 'parents', {'parents': [FATHER, MOTHER]})
    assert [d['person'] for d in declarations(api, app_id)] == ['Father']
    save(api, app_id, 'parents', {'parents': [FATHER, {**MOTHER, 'profession': 'labourer',
                                                        'occupation_type': 'Tailor', 'net_monthly_income': 15000}]})
    assert sorted(d['person'] for d in declarations(api, app_id)) == ['Father', 'Mother']


def test_employed_declaration_text_is_prefilled_and_keeps_official_wording(api, app_id):
    save(api, app_id, 'parents', {'parents': [FATHER, MOTHER]})
    printable = declarations(api, app_id)[0]['printable']
    assert printable['template'] == 'employed'
    assert printable['header'] == ('I, Muhammad Aslam bearing CNIC # 36302-1111111-1 hereby, truthfully state the '
                                   'following:')
    assert printable['items'] == [
        '1. I am a salaried/Retired person.',
        '2. The name of my Department/organization is WAPDA Multan',
        f'3. The address of Department/organization is {BLANK}',
        '4. My Designation is Assistant BPS-15',
        f'5. Department/organization location is owned by {BLANK}',
        '6. My total Monthly income is Rs. 72,000',
    ]
    assert printable['closing'] == CLOSING
    assert 'salary slip' in printable['note']
    # the student's details sit outside the official text
    assert printable['student_reference'] == {'student_name': 'Ali Khan', 'registration_id': '233585',
                                              'application_no': app_id}
    official = ' '.join([printable['header'], *printable['items'], printable['closing']])
    assert 'Ali Khan' not in official and '233585' not in official


@pytest.mark.parametrize('profession,template,expected', [
    ('business', 'self_employed', '6. My total annual income from this business/shop is Rs. 960,000'),
    ('labourer', 'labourer', '3. My monthly income from all sources is Rs. 72,000.'),
])
def test_other_templates(api, app_id, profession, template, expected):
    save(api, app_id, 'parents', {'parents': [{**FATHER, 'profession': profession}, MOTHER]})
    printable = declarations(api, app_id)[0]['printable']
    assert printable['template'] == template and expected in printable['items']


def test_farmer_template_uses_agricultural_land(api, app_id):
    save(api, app_id, 'parents', {'parents': [{**FATHER, 'profession': 'farmer'}, MOTHER]})
    save(api, app_id, 'assets', {'land_holdings': [{'category': 'agricultural', 'quantity': 1, 'size': '12 acres',
                                                    'location': 'Mouza Basti, Tehsil Shujabad'}]})
    item = declarations(api, app_id)[0]['printable']['items'][0]
    assert item == ('1. I, along with all my family members, own 12 acres of agricultural land situated at '
                    'Mouza Basti, Tehsil Shujabad')


# ---------- scans ----------

def upload_scan(api, app_id, declaration_id, file=None):
    return api.post(f'{BASE}{app_id}/declarations/{declaration_id}/scan/', {'file': file or pdf()},
                    format='multipart')


def test_scan_survives_resaving_parents_but_profession_change_clears_it(api, app_id,
                                                                       django_capture_on_commit_callbacks):
    save(api, app_id, 'parents', {'parents': [FATHER, MOTHER]})
    decl_id = declarations(api, app_id)[0]['id']
    assert upload_scan(api, app_id, decl_id).status_code == 200

    save(api, app_id, 'parents', {'parents': [{**FATHER, 'mobile': '03011112222'}, MOTHER]})
    decl = declarations(api, app_id)[0]
    assert decl['id'] == decl_id and decl['scan'] is not None

    with django_capture_on_commit_callbacks(execute=True):
        save(api, app_id, 'parents', {'parents': [{**FATHER, 'profession': 'business'}, MOTHER]})
    decl = declarations(api, app_id)[0]
    assert decl['template'] == 'self_employed' and decl['scan'] is None


def test_declaration_removed_when_parent_stops_earning(api, app_id):
    save(api, app_id, 'parents', {'parents': [FATHER, MOTHER]})
    save(api, app_id, 'parents', {'parents': [{**FATHER, 'profession': 'not_earning'}, MOTHER]})
    assert declarations(api, app_id) == []


def test_fake_scan_is_rejected(api, app_id):
    save(api, app_id, 'parents', {'parents': [FATHER, MOTHER]})
    decl_id = declarations(api, app_id)[0]['id']
    response = upload_scan(api, app_id, decl_id, SimpleUploadedFile('scan.pdf', b'not a pdf'))
    assert response.status_code == 400 and 'file' in response.json()


def test_scan_can_be_uploaded_after_submission_until_received(api, app_id, officer):
    fill_complete(api, app_id)
    api.post(f'{BASE}{app_id}/submit/')
    decl_id = declarations(api, app_id)[0]['id']
    assert upload_scan(api, app_id, decl_id).status_code == 200
    assert upload_scan(api, app_id, decl_id).status_code == 200  # replace still allowed

    officer.post(f'/api/v1/scholarships/declarations/{decl_id}/receive/', {}, format='json')
    response = upload_scan(api, app_id, decl_id)
    assert response.status_code == 403 and 'already received' in response.json()['detail']


def test_scan_can_still_be_added_if_original_arrived_first(api, app_id, officer):
    fill_complete(api, app_id)
    api.post(f'{BASE}{app_id}/submit/')
    decl_id = declarations(api, app_id)[0]['id']
    officer.post(f'/api/v1/scholarships/declarations/{decl_id}/receive/', {}, format='json')
    assert upload_scan(api, app_id, decl_id).status_code == 200


def test_scan_download_permissions(api, app_id, officer, dept):
    save(api, app_id, 'parents', {'parents': [FATHER, MOTHER]})
    decl_id = declarations(api, app_id)[0]['id']
    url = f'/api/v1/scholarships/declarations/{decl_id}/scan/'
    assert api.get(url).status_code == 404  # nothing uploaded yet
    upload_scan(api, app_id, decl_id)
    assert api.get(url).status_code == 200
    assert officer.get(url).status_code == 404  # still a draft
    Application.objects.filter(pk=app_id).update(status='placement_verification')
    assert officer.get(url).status_code == 200
    assert client_for(make_user('other@gmail.com', dept=dept)).get(url).status_code == 404
    dac = client_for(make_user('dac@au.edu.pk', role=Role.DAC_MEMBER, dept=dept))
    assert dac.get(url).status_code == 404  # not in the DAC queue yet
    Application.objects.filter(pk=app_id).update(status='dac_review')
    assert dac.get(url).status_code == 200
    assert APIClient().get(url).status_code == 401


# ---------- physical copy received ----------

def test_officer_marks_physical_copy_received_and_application_completes(api, app_id, officer):
    fill_complete(api, app_id)
    api.post(f'{BASE}{app_id}/submit/')
    decl_id = declarations(api, app_id)[0]['id']
    upload_scan(api, app_id, decl_id)

    response = officer.post(f'/api/v1/scholarships/declarations/{decl_id}/receive/', {}, format='json')
    assert response.status_code == 200
    assert response.json()['physical_received_on'] == timezone.localdate().isoformat()
    assert response.json()['physical_received_by'] == 'Ali Khan'  # the officer's name in this test

    completion = api.get(f'{BASE}{app_id}/').json()['completion']
    assert completion == {'form_submitted': True, 'declarations_required': 1, 'scans_uploaded': True,
                          'physical_copies_received': True, 'complete': True}

    undo = officer.delete(f'/api/v1/scholarships/declarations/{decl_id}/receive/')
    assert undo.status_code == 200 and undo.json()['physical_received_on'] is None
    assert api.get(f'{BASE}{app_id}/').json()['completion']['complete'] is False


def test_receipt_date_can_be_given_but_not_in_the_future(api, app_id, officer):
    fill_complete(api, app_id)
    api.post(f'{BASE}{app_id}/submit/')
    decl_id = declarations(api, app_id)[0]['id']
    url = f'/api/v1/scholarships/declarations/{decl_id}/receive/'
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    assert officer.post(url, {'received_on': tomorrow}, format='json').status_code == 400
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
    assert officer.post(url, {'received_on': yesterday}, format='json').json()['physical_received_on'] == yesterday


def test_cannot_mark_received_before_submission(api, app_id, officer):
    save(api, app_id, 'parents', {'parents': [FATHER, MOTHER]})
    decl_id = declarations(api, app_id)[0]['id']
    assert officer.post(f'/api/v1/scholarships/declarations/{decl_id}/receive/', {},
                        format='json').status_code == 400


@pytest.mark.parametrize('role', [Role.STUDENT, Role.DAC_MEMBER, Role.DIRECTOR])
def test_only_reviewing_staff_can_mark_received(api, app_id, dept, role):
    save(api, app_id, 'parents', {'parents': [FATHER, MOTHER]})
    decl_id = Declaration.objects.get().pk
    client = api if role == Role.STUDENT else client_for(make_user(f'{role}@au.edu.pk', role=role, dept=dept))
    assert client.post(f'/api/v1/scholarships/declarations/{decl_id}/receive/', {},
                       format='json').status_code == 403
