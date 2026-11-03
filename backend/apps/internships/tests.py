"""Internship requests (Phase 8): the student's form, offer letter, submit/withdraw, and the chain itself."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User
from apps.notifications.models import Notification
from apps.workflow.engine import WorkflowError

from .models import InternshipRequest
from .workflow import CHAIN, perform

BASE = '/api/v1/internships/requests/'
PDF = b'%PDF-1.4\n%%EOF\n'


@pytest.fixture(autouse=True)
def temp_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def make(email, role=Role.STUDENT, dept=None, name='Ali Khan'):
    return User.objects.create_user(email=email, password='x', full_name=name, role=role, department=dept,
                                    is_email_verified=True)


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def complete(**over):
    start = timezone.localdate() + timedelta(days=14)
    return {'organisation': 'Systems Ltd', 'organisation_address': 'Plot 5, Industrial Area', 'city': 'Lahore',
            'contact_name': 'Sara Malik', 'contact_designation': 'HR Manager', 'contact_email': 'hr@systems.pk',
            'contact_phone': '0300-1234567', 'field': 'Software development', 'role_title': 'Backend intern',
            'start_date': start.isoformat(), 'end_date': (start + timedelta(weeks=8, days=-1)).isoformat(),
            'mode': 'onsite', 'relevance': 'The internship covers Django web services, databases and testing, '
                                           'which are core courses of my BS Software Engineering.', **over}


@pytest.fixture
def cs(db):
    return Department.objects.create(name='Computer Science', code='CS')


@pytest.fixture
def people(cs):
    return {'student': make('ali@gmail.com', dept=cs), 'dic': make('dic@au.edu.pk', Role.DIC, cs, 'Dr Dic'),
            'po': make('po@au.edu.pk', Role.PLACEMENT_OFFICER, name='Sana Placement'),
            'sup': make('sup@au.edu.pk', Role.FACULTY_SUPERVISOR, cs, 'Dr Supervisor')}


@pytest.fixture
def student(people):
    return as_user(people['student'])


def submitted(student, **over):
    req_id = student.post(BASE, complete(**over), format='json').json()['id']
    response = student.post(f'{BASE}{req_id}/actions/', {'action': 'submit'}, format='json')
    assert response.status_code == 200, response.json()
    return req_id


# ---------- the student's request ----------

def test_draft_is_saved_and_checked_for_format(student):
    created = student.post(BASE, {'organisation': 'Systems Ltd'}, format='json')
    assert created.status_code == 201 and created.json()['status'] == 'draft'
    req_id = created.json()['id']
    phone = student.patch(f'{BASE}{req_id}/', {'contact_phone': '12ab'}, format='json')
    assert phone.status_code == 400 and 'contact_phone' in phone.json()
    dates = student.patch(f'{BASE}{req_id}/', {'start_date': '2027-02-01', 'end_date': '2027-01-01'}, format='json')
    assert dates.status_code == 400 and 'end_date' in dates.json()
    assert student.patch(f'{BASE}{req_id}/', {'city': 'Multan'}, format='json').json()['city'] == 'Multan'


def test_submit_needs_a_complete_request(student):
    req_id = student.post(BASE, {'organisation': 'Systems Ltd'}, format='json').json()['id']
    response = student.post(f'{BASE}{req_id}/actions/', {'action': 'submit'}, format='json')
    assert response.status_code == 400 and 'contact_email' in response.json()['errors']
    long = complete()
    long['end_date'] = (timezone.localdate() + timedelta(weeks=40)).isoformat()
    student.patch(f'{BASE}{req_id}/', long, format='json')
    errors = student.get(f'{BASE}{req_id}/readiness/').json()['errors']
    assert list(errors) == ['end_date'] and '4 to 26 weeks' in errors['end_date'][0]


def test_submit_locks_the_form_and_tells_the_dic(student, people):
    other_dic = make('dic.ee@au.edu.pk', Role.DIC, Department.objects.create(name='EE', code='EE'))
    req_id = submitted(student)
    data = student.get(f'{BASE}{req_id}/').json()
    assert data['status'] == 'dic_review' and data['submitted_at'] and data['weeks'] == 8
    assert [a['action'] for a in data['available_actions']] == ['withdraw']
    assert student.patch(f'{BASE}{req_id}/', {'city': 'X'}, format='json').status_code == 403
    assert Notification.objects.filter(recipient=people['dic'], link=f'/internship-review/{req_id}').exists()
    assert not Notification.objects.filter(recipient=other_dic).exists()
    assert Notification.objects.get(recipient=people['student']).title.endswith(
        'is with your Departmental Internship Coordinator')


def test_one_open_request_at_a_time_and_withdraw(student):
    req_id = submitted(student)
    assert student.post(BASE, complete(), format='json').status_code == 400
    response = student.post(f'{BASE}{req_id}/actions/', {'action': 'withdraw'}, format='json')
    assert response.json()['status'] == 'withdrawn'
    assert student.post(BASE, complete(), format='json').status_code == 201


def test_students_cannot_take_staff_actions_or_see_others(student, cs):
    req_id = submitted(student)
    assert student.post(f'{BASE}{req_id}/actions/', {'action': 'approve'}, format='json').status_code == 403
    stranger = as_user(make('other@gmail.com', dept=cs))
    assert stranger.get(f'{BASE}{req_id}/').status_code == 404


def test_offer_letter_upload_and_download(student, people, cs):
    req_id = student.post(BASE, complete(), format='json').json()['id']
    bad = student.post(f'{BASE}{req_id}/offer-letter/', {'file': SimpleUploadedFile('x.pdf', b'MZ')},
                       format='multipart')
    assert bad.status_code == 400 and 'file' in bad.json()
    ok = student.post(f'{BASE}{req_id}/offer-letter/', {'file': SimpleUploadedFile('offer.pdf', PDF)},
                      format='multipart')
    url = ok.json()['offer_letter']['download_url']
    assert ok.status_code == 200 and ok.json()['offer_letter']['name'] == 'offer.pdf'
    assert student.get(url).status_code == 200
    assert as_user(people['dic']).get(url).status_code == 404  # still a draft
    student.post(f'{BASE}{req_id}/actions/', {'action': 'submit'}, format='json')
    assert as_user(people['dic']).get(url).status_code == 200
    assert as_user(make('x@gmail.com', dept=cs)).get(url).status_code == 404


# ---------- the chain (screens for each role come in Phases 9-11) ----------

def test_the_whole_internship_chain(student, people):
    req_id = submitted(student)
    with pytest.raises(ValidationError):
        perform(req_id, 'approve', people['dic'])  # supervisor not assigned yet
    InternshipRequest.objects.filter(pk=req_id).update(field_relevant=True, faculty_supervisor=people['sup'])
    perform(req_id, 'approve', people['dic'])
    with pytest.raises(ValidationError):
        perform(req_id, 'send_for_review', people['po'])  # no addressee yet
    InternshipRequest.objects.filter(pk=req_id).update(addressee_name='Sara Malik', addressee_designation='HR Manager')
    perform(req_id, 'send_for_review', people['po'])
    with pytest.raises(WorkflowError):
        perform(req_id, 'approve_letter', make('sup2@au.edu.pk', Role.FACULTY_SUPERVISOR))  # not assigned to them
    perform(req_id, 'return_letter', people['sup'], remarks='Add the internship dates.')
    perform(req_id, 'send_for_review', people['po'])
    perform(req_id, 'approve_letter', people['sup'])
    perform(req_id, 'confirm', people['dic'])
    req = perform(req_id, 'issue', people['po'])
    assert req.status == 'issued' and CHAIN.is_final('issued')
    actions = list(req.status_history.values_list('action', flat=True))
    assert actions == ['submit', 'approve', 'send_for_review', 'return_letter', 'send_for_review', 'approve_letter',
                       'confirm', 'issue']
