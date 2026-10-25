from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User

from .models import Application, ScholarshipCycle

PASSWORD = 'Str0ng-Passw0rd!'
BASE = '/api/v1/scholarships/applications/'


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


@pytest.fixture
def student(dept):
    return make_user('ali@gmail.com', dept=dept, registration_id='233585')


@pytest.fixture
def api(student):
    client = APIClient()
    client.force_authenticate(student)
    return client


@pytest.fixture
def app_id(api, cycle):
    return api.post(BASE, {'cycle': cycle.pk}, format='json').json()['id']


def save(api, app_id, section, data):
    return api.patch(f'{BASE}{app_id}/sections/{section}/', data, format='json')


# ---------- profile ----------

def test_student_sets_registration_id_on_profile(dept):
    user = make_user('new@gmail.com', dept=dept)
    client = APIClient()
    client.force_authenticate(user)
    assert client.patch('/api/v1/auth/me/', {'registration_id': '1234'}, format='json').status_code == 400
    response = client.patch('/api/v1/auth/me/', {'registration_id': '2335851'}, format='json')
    assert response.status_code == 200 and response.json()['registration_id'] == '2335851'


def test_registration_id_cannot_be_taken_twice(student, dept):
    other = make_user('other@gmail.com', dept=dept)
    client = APIClient()
    client.force_authenticate(other)
    response = client.patch('/api/v1/auth/me/', {'registration_id': '233585'}, format='json')
    assert response.status_code == 400 and 'already linked' in str(response.json())


# ---------- cycles and creating a draft ----------

def test_open_cycles_lists_only_open_ones(api, cycle):
    ScholarshipCycle.objects.create(name='Old', opens_on=date(2020, 1, 1), closes_on=date(2020, 2, 1))
    assert [c['name'] for c in api.get('/api/v1/scholarships/cycles/open/').json()] == ['Fall-26']


def test_creating_a_draft_prefills_known_student_data(api, cycle, student):
    response = api.post(BASE, {'cycle': cycle.pk}, format='json')
    assert response.status_code == 201
    data = response.json()
    assert data['status'] == 'draft' and data['is_editable']
    assert data['applicant_name'] == 'Ali Khan'
    assert data['email'] == 'ali@gmail.com'
    assert data['registration_id'] == '233585'
    assert data['department'] == 'Computer Science'
    assert data['cycle']['name'] == 'Fall-26'


def test_only_one_application_per_cycle(api, cycle, app_id):
    response = api.post(BASE, {'cycle': cycle.pk}, format='json')
    assert response.status_code == 400 and 'already have an application' in str(response.json())


def test_cannot_apply_to_a_closed_cycle(api):
    closed = ScholarshipCycle.objects.create(name='Old', opens_on=date(2020, 1, 1), closes_on=date(2020, 2, 1))
    response = api.post(BASE, {'cycle': closed.pk}, format='json')
    assert response.status_code == 400 and 'not open' in str(response.json())


# ---------- permissions ----------

@pytest.mark.parametrize('role', [r for r in Role.values if r != Role.STUDENT])
def test_staff_roles_cannot_use_the_student_application_api(cycle, dept, role):
    client = APIClient()
    client.force_authenticate(make_user(f'{role}@au.edu.pk', role=role, dept=dept))
    assert client.get(BASE).status_code == 403
    assert client.post(BASE, {'cycle': cycle.pk}, format='json').status_code == 403


def test_anonymous_user_gets_401(db):
    assert APIClient().get(BASE).status_code == 401


def test_students_cannot_see_or_edit_each_others_applications(app_id, dept):
    intruder = APIClient()
    intruder.force_authenticate(make_user('intruder@gmail.com', dept=dept))
    assert intruder.get(f'{BASE}{app_id}/').status_code == 404
    assert save(intruder, app_id, 'personal', {'domicile': 'Hacked'}).status_code == 404
    assert intruder.get(BASE).json()['count'] == 0


def test_submitted_application_cannot_be_edited(api, app_id):
    Application.objects.filter(pk=app_id).update(status='placement_verification')
    response = save(api, app_id, 'personal', {'domicile': 'Multan'})
    assert response.status_code == 403 and 'no longer be changed' in response.json()['detail']


def test_unknown_section_is_404(api, app_id):
    assert save(api, app_id, 'hobbies', {}).status_code == 404


def test_student_cannot_change_status_through_a_section(api, app_id):
    save(api, app_id, 'personal', {'domicile': 'Multan', 'status': 'approved'})
    assert Application.objects.get(pk=app_id).status == 'draft'


# ---------- personal section validation ----------

def test_partial_drafts_save_without_required_fields(api, app_id):
    response = save(api, app_id, 'personal', {'domicile': 'Multan'})
    assert response.status_code == 200 and response.json()['domicile'] == 'Multan'


def test_cnic_and_phone_are_normalised(api, app_id):
    data = save(api, app_id, 'personal', {'cnic': '3630212345671', 'mobile': '0300-123 4567',
                                          'tel_residence': '061-2345678'}).json()
    assert data['cnic'] == '36302-1234567-1'
    assert data['mobile'] == '03001234567'
    assert data['tel_residence'] == '0612345678'


@pytest.mark.parametrize('field,value', [
    ('cnic', '12345'), ('cnic', 'abcde-fghijkl-m'),
    ('mobile', '12345'), ('mobile', '04001234567'),
    ('tel_residence', '12'),
    ('registration_id', '12345'), ('registration_id', '123456789'),
    ('gender', 'other'),
])
def test_personal_field_errors_are_reported_per_field(api, app_id, field, value):
    response = save(api, app_id, 'personal', {field: value})
    assert response.status_code == 400 and field in response.json()


def test_age_must_be_between_15_and_60(api, app_id):
    today = timezone.localdate()
    too_young = today.replace(year=today.year - 10).isoformat()
    response = save(api, app_id, 'personal', {'date_of_birth': too_young})
    assert response.status_code == 400 and 'date_of_birth' in response.json()
    ok = save(api, app_id, 'personal', {'date_of_birth': today.replace(year=today.year - 20).isoformat()})
    assert ok.json()['age'] == 20


def test_cnic_cannot_be_reused_in_the_same_cycle(api, app_id, cycle, dept):
    other = make_user('sister@gmail.com', dept=dept)
    Application.objects.create(cycle=cycle, student=other, cnic='36302-1234567-1')
    response = save(api, app_id, 'personal', {'cnic': '36302-1234567-1'})
    assert response.status_code == 400 and 'already used' in str(response.json()['cnic'])


# ---------- nested sections ----------

def test_household_rows_are_replaced_and_checked_against_total(api, app_id):
    members = [{'name': 'Aslam', 'relationship': 'father'}, {'name': 'Bano', 'relationship': 'mother'}]
    data = save(api, app_id, 'household', {'total_family_members': 4, 'household_members': members}).json()
    assert len(data['household_members']) == 2
    data = save(api, app_id, 'household', {'household_members': members[:1]}).json()
    assert len(data['household_members']) == 1  # replaced, not appended
    too_many = save(api, app_id, 'household', {'total_family_members': 1, 'household_members': members})
    assert too_many.status_code == 400 and 'household_members' in too_many.json()


def test_row_errors_point_at_the_row_and_field(api, app_id):
    rows = [{'name': 'Aslam', 'relationship': 'father'}, {'name': '', 'relationship': 'uncle-ish'}]
    errors = save(api, app_id, 'household', {'household_members': rows}).json()['household_members']
    # only the failing row is reported, keyed by its position in the list
    assert list(errors) == ['1'] and set(errors['1']) == {'name', 'relationship'}


def test_parents_validation(api, app_id):
    bad = save(api, app_id, 'parents', {'parents': [
        {'role': 'father', 'name': 'Aslam', 'cnic': '123', 'gross_monthly_income': 50000,
         'net_monthly_income': 50000}]})
    assert bad.status_code == 400
    assert 'cnic' in bad.json()['parents']['0']

    net_too_high = save(api, app_id, 'parents', {'parents': [
        {'role': 'father', 'gross_monthly_income': 50000, 'net_monthly_income': 60000}]})
    assert 'net_monthly_income' in net_too_high.json()['parents']['0']

    dup = save(api, app_id, 'parents', {'parents': [{'role': 'father'}, {'role': 'father'}]})
    assert dup.status_code == 400

    ok = save(api, app_id, 'parents', {'parents': [
        {'role': 'father', 'name': 'Aslam', 'cnic': '3630212345671', 'profession': 'employed',
         'gross_monthly_income': 60000, 'net_monthly_income': 55000},
        {'role': 'mother', 'name': 'Bano', 'status': 'alive', 'profession': 'not_earning'}]})
    assert ok.status_code == 200
    assert ok.json()['parents'][0]['cnic'] == '36302-1234567-1'


def test_applicant_net_income_cannot_exceed_gross(api, app_id):
    response = save(api, app_id, 'income', {'applicant_gross_income': 1000, 'applicant_net_income': 2000})
    assert response.status_code == 400 and 'applicant_net_income' in response.json()


def test_money_cannot_be_negative_or_text(api, app_id):
    assert save(api, app_id, 'expenses', {'medical_monthly': -5}).status_code == 400
    assert save(api, app_id, 'expenses', {'misc_monthly': 'a lot'}).status_code == 400


def test_education_rules(api, app_id):
    base = {'level': 'intermediate', 'institute': 'Govt College Multan', 'from_month': '2020-09-01',
            'to_month': '2022-06-01'}
    assert save(api, app_id, 'education', {'education_records': [{**base, 'cgpa': '4.5'}]}).status_code == 400
    assert save(api, app_id, 'education', {'education_records': [{**base, 'percentage': '101'}]}).status_code == 400
    assert save(api, app_id, 'education', {'education_records': [base]}).status_code == 400  # no result
    assert save(api, app_id, 'education', {'education_records': [
        {**base, 'to_month': '2019-01-01', 'division': '1st'}]}).status_code == 400
    assert save(api, app_id, 'education', {'education_records': [{**base, 'percentage': '85.5'}]}).status_code == 200


def test_undertaking_records_date_when_accepted(api, app_id):
    data = save(api, app_id, 'undertaking', {'undertaking_accepted': True, 'undertaking_name': 'Ali Khan'}).json()
    assert data['undertaking_date'] == timezone.localdate().isoformat()
    data = save(api, app_id, 'undertaking', {'undertaking_accepted': False}).json()
    assert data['undertaking_date'] is None


# ---------- calculations ----------

def test_totals_follow_the_agreed_formulas(api, app_id):
    save(api, app_id, 'household', {'studying_members': [
        {'name': 'Sara', 'relation': 'sister', 'institute': 'BZU Multan', 'fee_per_month': 5000}]})
    save(api, app_id, 'income', {
        'applicant_gross_income': 10000, 'applicant_net_income': 8000,
        'earning_members': [{'name': 'Aslam', 'relationship': 'father', 'gross_pay': 60000, 'net_pay': 50000},
                            {'name': 'Bilal', 'relationship': 'brother', 'gross_pay': 30000, 'net_pay': 25000}],
        'asset_income': [{'source': 'property_rent', 'father': 7000, 'mother': 3000}]})
    save(api, app_id, 'accommodation', {'accommodation_status': 'rented', 'monthly_rent': 15000})
    summary = save(api, app_id, 'expenses', {
        'utility_months': [{'month_index': 1, 'electricity': 6000, 'gas': 1000},
                           {'month_index': 2, 'electricity': 8000, 'gas': 2000},
                           {'month_index': 3, 'electricity': 7000, 'gas': 1500, 'water': 500}],
        'medical_monthly': 4000, 'misc_monthly': 6000}).json()['summary']

    assert summary['total_family_earning_gross'] == 100000          # Q10.1: 60k + 30k + 10k
    assert summary['total_studying_fees'] == 5000                   # Q11.1
    assert summary['monthly_asset_income'] == 10000                 # Q24.1
    assert summary['total_monthly_income'] == 93000                 # Q25.1: net 50k + 25k + 8k + assets 10k
    assert summary['total_annual_income'] == 93000 * 12             # Q25.2
    assert summary['utilities_monthly_average'] == 8667             # (7000 + 10000 + 9000) / 3
    assert summary['total_monthly_expenditure'] == 5000 + 15000 + 8667 + 4000 + 6000
    assert summary['net_monthly_disposable'] == 93000 - 38667       # Q30
    assert summary['net_annual_disposable'] == (93000 - 38667) * 12  # Q31


def test_empty_draft_has_zero_totals(api, app_id):
    summary = api.get(f'{BASE}{app_id}/').json()['summary']
    assert summary['total_monthly_income'] == 0 and summary['net_monthly_disposable'] == 0
