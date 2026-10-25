import io
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User

from .models import Application, ApplicationDocument, ParentGuardian, ScholarshipCycle

PASSWORD = 'Str0ng-Passw0rd!'
BASE = '/api/v1/scholarships/applications/'


# ---------- sample files ----------

def pdf_bytes():
    return b'%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n'


def image_bytes(fmt):
    buffer = io.BytesIO()
    Image.new('RGB', (20, 20), 'white').save(buffer, fmt)
    return buffer.getvalue()


def upload(name, content, content_type='application/octet-stream'):
    return SimpleUploadedFile(name, content, content_type=content_type)


# ---------- fixtures ----------

@pytest.fixture(autouse=True)
def temp_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def dept(db):
    return Department.objects.create(name='Computer Science', code='CS')


@pytest.fixture
def cycle(db):
    today = timezone.localdate()
    return ScholarshipCycle.objects.create(name='Fall-26', opens_on=today - timedelta(days=1),
                                           closes_on=today + timedelta(days=30))


def make_user(email, role=Role.STUDENT, dept=None):
    return User.objects.create_user(email=email, password=PASSWORD, full_name='Ali Khan', role=role,
                                    department=dept, is_email_verified=True)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def student(dept):
    return make_user('ali@gmail.com', dept=dept)


@pytest.fixture
def api(student):
    return client_for(student)


@pytest.fixture
def app_id(api, cycle):
    return api.post(BASE, {'cycle': cycle.pk}, format='json').json()['id']


def post_file(api, app_id, slot, file):
    return api.post(f'{BASE}{app_id}/documents/', {'slot': slot, 'file': file}, format='multipart')


def checklist(api, app_id):
    return {entry['slot']: entry for entry in api.get(f'{BASE}{app_id}/documents/').json()}


# ---------- accepted files ----------

@pytest.mark.parametrize('name,content,expected_type,ext', [
    ('statement.pdf', pdf_bytes(), 'application/pdf', 'pdf'),
    ('cnic.PNG', image_bytes('PNG'), 'image/png', 'png'),
    ('bill photo.jpeg', image_bytes('JPEG'), 'image/jpeg', 'jpg'),
])
def test_pdf_png_and_jpg_are_accepted(api, app_id, student, temp_media, name, content, expected_type, ext):
    response = post_file(api, app_id, 'cnic_copies', upload(name, content))
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data['original_name'] == name
    assert data['content_type'] == expected_type
    assert data['uploaded_by'] == 'Ali Khan'

    doc = ApplicationDocument.objects.get(pk=data['id'])
    assert doc.uploaded_by == student and doc.slot == 'cnic_copies'
    # stored under the student and application with a system-generated name
    assert re.fullmatch(rf'scholarships/{student.pk}/{app_id}/cnic_copies/[0-9a-f]{{32}}\.{ext}', doc.file.name)
    assert (Path(temp_media) / doc.file.name).exists()


def test_extension_comes_from_real_type_not_the_name(api, app_id):
    data = post_file(api, app_id, 'domicile', upload('scan.pdf', image_bytes('PNG'))).json()
    doc = ApplicationDocument.objects.get(pk=data['id'])
    assert data['content_type'] == 'image/png' and doc.file.name.endswith('.png')


# ---------- rejected files ----------

@pytest.mark.parametrize('name,content', [
    ('notes.pdf', b'just some text pretending to be a pdf'),
    ('virus.exe', b'MZ\x90\x00\x03\x00\x00\x00'),
    ('picture.gif', b'GIF89a\x01\x00\x01\x00'),
    ('broken.png', b'\x89PNG\r\n\x1a\n' + b'not really an image'),
    ('broken.jpg', b'\xff\xd8\xff' + b'garbage'),
    ('empty.pdf', b''),
])
def test_files_are_checked_by_their_real_content(api, app_id, temp_media, name, content):
    response = post_file(api, app_id, 'cnic_copies', upload(name, content, 'application/pdf'))
    assert response.status_code == 400 and 'file' in response.json()
    assert ApplicationDocument.objects.count() == 0
    assert not any(p.is_file() for p in Path(temp_media).rglob('*'))


def test_files_over_5_mb_are_rejected(api, app_id):
    big = pdf_bytes() + b'0' * (5 * 1024 * 1024)
    response = post_file(api, app_id, 'cnic_copies', upload('big.pdf', big))
    assert response.status_code == 400 and 'limit is 5 MB' in str(response.json())


def test_unknown_slot_is_rejected(api, app_id):
    response = post_file(api, app_id, 'passport', upload('a.pdf', pdf_bytes()))
    assert response.status_code == 400 and 'slot' in response.json()


# ---------- limits per slot ----------

def test_slot_limit_is_5_files_but_6_for_bank_statements(api, app_id):
    for i in range(5):
        assert post_file(api, app_id, 'utility_bills', upload(f'{i}.pdf', pdf_bytes())).status_code == 201
    sixth = post_file(api, app_id, 'utility_bills', upload('6.pdf', pdf_bytes()))
    assert sixth.status_code == 400 and 'maximum of 5' in str(sixth.json())

    for i in range(6):
        assert post_file(api, app_id, 'bank_statements', upload(f'{i}.pdf', pdf_bytes())).status_code == 201
    assert post_file(api, app_id, 'bank_statements', upload('7.pdf', pdf_bytes())).status_code == 400


# ---------- replace and delete ----------

def test_replace_keeps_the_slot_and_removes_the_old_file(api, app_id, temp_media, django_capture_on_commit_callbacks):
    doc_id = post_file(api, app_id, 'domicile', upload('old.pdf', pdf_bytes())).json()['id']
    old_path = Path(temp_media) / ApplicationDocument.objects.get(pk=doc_id).file.name

    with django_capture_on_commit_callbacks(execute=True):  # old file is deleted only after commit
        response = api.put(f'{BASE}{app_id}/documents/{doc_id}/', {'file': upload('new.jpg', image_bytes('JPEG'))},
                           format='multipart')
    assert response.status_code == 200
    doc = ApplicationDocument.objects.get(pk=doc_id)
    assert doc.slot == 'domicile' and doc.original_name == 'new.jpg' and doc.content_type == 'image/jpeg'
    assert not old_path.exists() and (Path(temp_media) / doc.file.name).exists()


def test_replace_with_a_bad_file_keeps_the_original(api, app_id):
    doc_id = post_file(api, app_id, 'domicile', upload('old.pdf', pdf_bytes())).json()['id']
    response = api.put(f'{BASE}{app_id}/documents/{doc_id}/', {'file': upload('bad.pdf', b'nope')},
                       format='multipart')
    assert response.status_code == 400
    assert ApplicationDocument.objects.get(pk=doc_id).original_name == 'old.pdf'


def test_delete_removes_record_and_file(api, app_id, temp_media, django_capture_on_commit_callbacks):
    doc_id = post_file(api, app_id, 'domicile', upload('a.pdf', pdf_bytes())).json()['id']
    path = Path(temp_media) / ApplicationDocument.objects.get(pk=doc_id).file.name
    with django_capture_on_commit_callbacks(execute=True):
        assert api.delete(f'{BASE}{app_id}/documents/{doc_id}/').status_code == 204
    assert not ApplicationDocument.objects.filter(pk=doc_id).exists() and not path.exists()


def test_files_are_locked_after_submission(api, app_id):
    doc_id = post_file(api, app_id, 'domicile', upload('a.pdf', pdf_bytes())).json()['id']
    Application.objects.filter(pk=app_id).update(status='pending')
    assert post_file(api, app_id, 'domicile', upload('b.pdf', pdf_bytes())).status_code == 403
    assert api.put(f'{BASE}{app_id}/documents/{doc_id}/', {'file': upload('c.pdf', pdf_bytes())},
                   format='multipart').status_code == 403
    assert api.delete(f'{BASE}{app_id}/documents/{doc_id}/').status_code == 403
    assert api.get(f'{BASE}{app_id}/documents/').status_code == 200  # can still view


# ---------- downloads and permissions ----------

def test_owner_can_download_their_file(api, app_id):
    doc = post_file(api, app_id, 'domicile', upload('Domicile Scan.pdf', pdf_bytes())).json()
    response = api.get(doc['download_url'])
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    assert 'Domicile Scan.pdf' in response['Content-Disposition']
    assert response['Cache-Control'] == 'private, no-store'
    assert b''.join(response.streaming_content) == pdf_bytes()


@pytest.mark.parametrize('role', [Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR])
def test_reviewing_staff_can_download_any_file(api, app_id, dept, role):
    url = post_file(api, app_id, 'domicile', upload('a.pdf', pdf_bytes())).json()['download_url']
    assert client_for(make_user(f'{role}@au.edu.pk', role=role, dept=dept)).get(url).status_code == 200


@pytest.mark.parametrize('role', [Role.STUDENT, Role.DAC_MEMBER, Role.DIRECTOR, Role.FINANCE_OFFICER])
def test_other_users_cannot_download(api, app_id, dept, role):
    url = post_file(api, app_id, 'domicile', upload('a.pdf', pdf_bytes())).json()['download_url']
    assert client_for(make_user(f'{role}.x@au.edu.pk', role=role, dept=dept)).get(url).status_code == 404


def test_anonymous_cannot_download(api, app_id):
    url = post_file(api, app_id, 'domicile', upload('a.pdf', pdf_bytes())).json()['download_url']
    assert APIClient().get(url).status_code == 401


def test_other_students_cannot_upload_or_list(app_id, dept):
    intruder = client_for(make_user('intruder@gmail.com', dept=dept))
    assert post_file(intruder, app_id, 'domicile', upload('a.pdf', pdf_bytes())).status_code == 404
    assert intruder.get(f'{BASE}{app_id}/documents/').status_code == 404


def test_media_folder_is_not_publicly_served(api, app_id, client):
    doc = ApplicationDocument.objects.get(pk=post_file(api, app_id, 'domicile', upload('a.pdf', pdf_bytes())).json()['id'])
    assert client.get(f'/media/{doc.file.name}').status_code == 404


# ---------- checklist rules ----------

def test_checklist_has_every_slot_with_labels_and_always_required_items(api, app_id):
    items = checklist(api, app_id)
    assert len(items) == 17
    assert items['domicile']['label'].startswith('2. Domicile')
    always = {s for s, e in items.items() if e['kind'] == 'always'}
    assert always == {'cnic_copies', 'domicile', 'bank_statements', 'fee_receipts', 'utility_bills', 'result_cards'}
    assert all(items[s]['required'] and items[s]['missing'] for s in always)
    assert {s for s, e in items.items() if e['kind'] == 'optional'} == {
        'other_income', 'hostel_proof', 'transport_fee', 'divorce_certificate'}
    assert items['bank_statements']['max_files'] == 6 and items['domicile']['max_files'] == 5


def test_missing_flag_clears_after_upload(api, app_id):
    post_file(api, app_id, 'domicile', upload('a.pdf', pdf_bytes()))
    entry = checklist(api, app_id)['domicile']
    assert entry['missing'] is False and len(entry['files']) == 1


def test_conditional_slots_follow_the_students_answers(api, app_id):
    conditional = ['salary_certificate', 'salary_slip', 'sibling_income', 'previous_scholarships',
                   'medical_bills', 'rent_agreement', 'death_certificate']
    items = checklist(api, app_id)
    assert not any(items[s]['required'] for s in conditional)

    def section(name, data):
        assert api.patch(f'{BASE}{app_id}/sections/{name}/', data, format='json').status_code == 200

    section('parents', {'parents': [{'role': 'father', 'status': 'deceased'},
                                    {'role': 'mother', 'profession': 'employed'}]})
    section('income', {'earning_members': [{'name': 'Bilal', 'relationship': 'brother', 'gross_pay': 30000}]})
    section('education', {'other_scholarships': True})
    section('expenses', {'medical_monthly': 2000})
    section('accommodation', {'accommodation_status': 'rented'})

    items = checklist(api, app_id)
    assert all(items[s]['required'] for s in conditional), {s: items[s]['required'] for s in conditional}
    assert 'rented' in items['rent_agreement']['reason']


def test_retired_parent_requires_salary_documents_but_not_earning_one(api, app_id):
    application = Application.objects.get(pk=app_id)
    ParentGuardian.objects.create(application=application, role='father', profession='retired')
    assert checklist(api, app_id)['salary_slip']['required']
    ParentGuardian.objects.filter(application=application).update(profession='not_earning')
    assert not checklist(api, app_id)['salary_slip']['required']
