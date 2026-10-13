import re
from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Department, Role, User
from apps.documents.paths import declaration_scan_path, scholarship_document_path

from .choices import DeclarationTemplate, DocumentSlot, LifeStatus, ParentRole, Profession
from .models import (Application, ApplicationDocument, Declaration, EarningMember, EducationRecord,
                     ParentGuardian, ScholarshipCycle)

PASSWORD = 'Str0ng-Passw0rd!'


@pytest.fixture
def dept(db):
    return Department.objects.create(name='Computer Science', code='CS')


@pytest.fixture
def cycle(db):
    today = timezone.localdate()
    return ScholarshipCycle.objects.create(name='Fall-26', opens_on=today - timedelta(days=1),
                                           closes_on=today + timedelta(days=30))


def make_student(email, dept, **extra):
    return User.objects.create_user(email=email, password=PASSWORD, full_name='Ali Khan', role=Role.STUDENT,
                                    department=dept, is_email_verified=True, **extra)


# ---------- registration ID on the profile ----------

@pytest.mark.parametrize('value', ['23358', '123456789', '23358a', 'abcdef', '1234 567'])
def test_registration_id_must_be_six_to_eight_digits(dept, value):
    user = User(email='a@x.com', full_name='Ali Khan', role=Role.STUDENT, department=dept, registration_id=value)
    user.set_password(PASSWORD)
    with pytest.raises(ValidationError) as err:
        user.full_clean()
    assert 'registration_id' in err.value.message_dict


@pytest.mark.parametrize('value', ['233585', '2335851', '23358512'])
def test_registration_id_accepts_six_to_eight_digits(dept, value):
    user = User(email='a@x.com', full_name='Ali Khan', role=Role.STUDENT, department=dept, registration_id=value)
    user.set_password(PASSWORD)
    user.full_clean()


def test_registration_id_is_unique_but_optional(dept):
    make_student('a@x.com', dept, registration_id='233585')
    make_student('b@x.com', dept)  # no registration ID yet
    make_student('c@x.com', dept)  # several students may still be missing one
    with pytest.raises(IntegrityError):
        make_student('d@x.com', dept, registration_id='233585')


# ---------- scholarship cycles ----------

def test_cycle_is_open_only_between_its_dates_and_when_active(cycle):
    today = timezone.localdate()
    assert cycle.is_open(today)
    assert not cycle.is_open(cycle.closes_on + timedelta(days=1))
    assert not cycle.is_open(cycle.opens_on - timedelta(days=1))
    cycle.is_active = False
    assert not cycle.is_open(today)


def test_cycle_closing_date_cannot_precede_opening_date(db):
    bad = ScholarshipCycle(name='Spring-27', opens_on=date(2027, 2, 1), closes_on=date(2027, 1, 1))
    with pytest.raises(ValidationError):
        bad.full_clean()


# ---------- applications ----------

def test_one_application_per_student_per_cycle(cycle, dept):
    student = make_student('a@x.com', dept)
    Application.objects.create(cycle=cycle, student=student)
    with pytest.raises(IntegrityError):
        Application.objects.create(cycle=cycle, student=student)


def test_same_student_may_apply_in_a_different_cycle(cycle, dept):
    student = make_student('a@x.com', dept)
    other = ScholarshipCycle.objects.create(name='Spring-27', opens_on=date(2027, 2, 1), closes_on=date(2027, 3, 1))
    Application.objects.create(cycle=cycle, student=student)
    Application.objects.create(cycle=other, student=student)


def test_applicant_cnic_is_unique_within_a_cycle(cycle, dept):
    a, b, c = (make_student(f'{n}@x.com', dept) for n in 'abc')
    Application.objects.create(cycle=cycle, student=a, cnic='12345-1234567-1')
    Application.objects.create(cycle=cycle, student=b)  # blank CNICs do not clash while drafting
    Application.objects.create(cycle=cycle, student=c)
    with pytest.raises(IntegrityError), transaction.atomic():
        Application.objects.filter(student=b).update(cnic='12345-1234567-1')


@pytest.mark.parametrize('field,value', [
    ('cnic', '1234512345671'), ('cnic', '12345-123456-1'),
    ('mobile', '3001234567'), ('mobile', '04001234567'),
    ('tel_residence', '1234'),
])
def test_application_contact_formats_are_validated(cycle, dept, field, value):
    app = Application(cycle=cycle, student=make_student('a@x.com', dept), **{field: value})
    with pytest.raises(ValidationError) as err:
        app.full_clean()
    assert field in err.value.message_dict


def test_valid_contact_formats_pass(cycle, dept):
    app = Application(cycle=cycle, student=make_student('a@x.com', dept), cnic='12345-1234567-1',
                      mobile='+923001234567', tel_residence='0612345678')
    app.full_clean()


def test_new_application_is_an_editable_draft_and_age_is_computed(cycle, dept):
    app = Application.objects.create(cycle=cycle, student=make_student('a@x.com', dept))
    assert app.status == 'draft' and app.is_editable
    today = timezone.localdate()
    app.date_of_birth = today.replace(year=today.year - 20)
    assert app.age == 20
    app.status = 'pending'
    assert not app.is_editable


def test_net_pay_cannot_exceed_gross(cycle, dept):
    app = Application.objects.create(cycle=cycle, student=make_student('a@x.com', dept))
    member = EarningMember(application=app, name='Father', relationship='father', gross_pay=50000, net_pay=60000)
    with pytest.raises(ValidationError):
        member.full_clean()


def test_education_record_rules(cycle, dept):
    app = Application.objects.create(cycle=cycle, student=make_student('a@x.com', dept))
    base = dict(application=app, level='intermediate', institute='Govt College Multan',
                from_month=date(2020, 9, 1), to_month=date(2022, 6, 1))
    with pytest.raises(ValidationError):  # no result given
        EducationRecord(**base).full_clean()
    with pytest.raises(ValidationError):  # CGPA above 4.00
        EducationRecord(**base, cgpa='4.10').full_clean()
    with pytest.raises(ValidationError):  # percentage above 100
        EducationRecord(**base, percentage='100.5').full_clean()
    with pytest.raises(ValidationError):  # finishes before it starts
        EducationRecord(**{**base, 'to_month': date(2019, 1, 1)}, division='1st').full_clean()
    EducationRecord(**base, percentage='85.5').full_clean()


# ---------- Form 2 template selection ----------

@pytest.mark.parametrize('profession,template', [
    (Profession.EMPLOYED, DeclarationTemplate.EMPLOYED),
    (Profession.RETIRED, DeclarationTemplate.EMPLOYED),
    (Profession.BUSINESS, DeclarationTemplate.SELF_EMPLOYED),
    (Profession.FARMER, DeclarationTemplate.FARMER),
    (Profession.LABOURER, DeclarationTemplate.LABOURER),
    (Profession.NOT_EARNING, None),
])
def test_declaration_template_follows_profession(cycle, dept, profession, template):
    app = Application.objects.create(cycle=cycle, student=make_student('a@x.com', dept))
    parent = ParentGuardian.objects.create(application=app, role=ParentRole.FATHER, profession=profession)
    assert parent.declaration_template == template


def test_deceased_parent_needs_no_declaration(cycle, dept):
    app = Application.objects.create(cycle=cycle, student=make_student('a@x.com', dept))
    parent = ParentGuardian.objects.create(application=app, role=ParentRole.FATHER,
                                           profession=Profession.EMPLOYED, status=LifeStatus.DECEASED)
    assert parent.declaration_template is None


def test_one_parent_record_per_role(cycle, dept):
    app = Application.objects.create(cycle=cycle, student=make_student('a@x.com', dept))
    ParentGuardian.objects.create(application=app, role=ParentRole.FATHER)
    with pytest.raises(IntegrityError):
        ParentGuardian.objects.create(application=app, role=ParentRole.FATHER)


# ---------- upload paths ----------

def test_upload_paths_are_per_student_and_application_with_system_names(cycle, dept):
    student = make_student('a@x.com', dept)
    app = Application.objects.create(cycle=cycle, student=student)
    doc = ApplicationDocument(application=app, slot=DocumentSlot.BANK_STATEMENTS)
    path = scholarship_document_path(doc, 'My Bank Statement (June).PDF')
    assert re.fullmatch(rf'scholarships/{student.pk}/{app.pk}/bank_statements/[0-9a-f]{{32}}\.pdf', path)

    parent = ParentGuardian.objects.create(application=app, role=ParentRole.FATHER)
    scan_path = declaration_scan_path(Declaration(application=app, parent=parent), 'stamp paper.jpg')
    assert re.fullmatch(rf'scholarships/{student.pk}/{app.pk}/declarations/[0-9a-f]{{32}}\.jpg', scan_path)


def test_uploads_use_the_configured_default_storage(settings):
    assert settings.STORAGES['default']['BACKEND'] == 'django.core.files.storage.FileSystemStorage'
    assert ApplicationDocument._meta.get_field('file').storage.__class__.__name__ == 'FileSystemStorage'


# ---------- Django admin ----------

@pytest.mark.parametrize('model', ['scholarshipcycle', 'application'])
def test_admin_pages_load(client, cycle, dept, model):
    admin = User.objects.create_superuser('root@au.edu.pk', PASSWORD, full_name='Root')
    app = Application.objects.create(cycle=cycle, student=make_student('a@x.com', dept))
    client.force_login(admin)
    assert client.get(f'/admin/scholarships/{model}/').status_code == 200
    obj_id = cycle.pk if model == 'scholarshipcycle' else app.pk
    assert client.get(f'/admin/scholarships/{model}/{obj_id}/change/').status_code == 200
