"""Notifications as a case moves: the student at every stage, staff when a case reaches their queue."""
import pytest
from django.core import mail
from django.utils import timezone

from apps.accounts.models import Role
from apps.notifications.models import Notification

from .models import Application
from .test_review import (REVIEW, STUDENT_BASE, act, client_for, cs, cycle, ee, make_complete, make_user,  # noqa: F401
                          officer, submitted_application, temp_media, verify_documents)


def titles(user):
    return list(Notification.objects.filter(recipient=user).order_by('pk').values_list('title', flat=True))


@pytest.fixture
def staff(cs, ee):
    return {
        'po2': make_user('po2@au.edu.pk', role=Role.PLACEMENT_OFFICER, name='Second Placement'),
        'dac_cs': make_user('dac.cs@au.edu.pk', role=Role.DAC_MEMBER, dept=cs),
        'dac_ee': make_user('dac.ee@au.edu.pk', role=Role.DAC_MEMBER, dept=ee),
        'director': make_user('director@au.edu.pk', role=Role.DIRECTOR),
        'registrar': make_user('registrar@au.edu.pk', role=Role.REGISTRAR, email_notifications=False),
        'vc': make_user('vc@au.edu.pk', role=Role.VICE_CHANCELLOR),
        'finance': make_user('finance@au.edu.pk', role=Role.FINANCE_OFFICER),
    }


def test_each_queue_hears_about_its_cases(cycle, cs, officer, staff, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    student = Application.objects.get(pk=app_id).student
    assert titles(staff['po2']) == [f'Application {app_id} is waiting for you (Placement verification)']
    assert any('waiting for you' in m.subject and m.to == ['po2@au.edu.pk'] for m in mail.outbox)

    make_complete(student_api, officer, app_id)
    verify_documents(officer, app_id)
    with django_capture_on_commit_callbacks(execute=True):
        act(officer, app_id, 'verify')
    assert titles(staff['dac_cs'])[-1].endswith('(DAC review)') and titles(staff['dac_ee']) == []

    Application.objects.filter(pk=app_id).update(interview_date=timezone.localdate())
    dac = client_for(staff['dac_cs'])
    act(dac, app_id, 'shortlist', percentage=60)
    assert titles(staff['po2'])[-1].endswith('(Awaiting forwarding)')
    act(officer, app_id, 'forward')
    act(client_for(staff['director']), app_id, 'approve')
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        act(client_for(staff['registrar']), app_id, 'approve')
    assert titles(staff['vc'])[-1].endswith('(VC review)')
    assert titles(staff['registrar'])[-1].endswith('(Registrar review)')  # in-app even with email off
    assert not any(m.to == ['registrar@au.edu.pk'] for m in mail.outbox)
    act(client_for(staff['vc']), app_id, 'approve')
    assert titles(staff['finance'])[-1].endswith('(Awaiting fee adjustment)')

    # The student is told in the app at every stage
    assert titles(student) == [f'Your application {app_id} {phrase}' for phrase in (
        'is with the Placement Office for verification', 'is with the Departmental Admission Committee',
        'was shortlisted by the Departmental Admission Committee', 'is with the Director', 'is with the Registrar',
        'is with the Vice Chancellor', 'was approved by the Vice Chancellor')]
    assert Notification.objects.filter(recipient=student).first().link == f'/scholarships/{app_id}/status'


def test_the_person_who_acted_is_not_notified(cycle, cs, staff):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    Application.objects.filter(pk=app_id).update(status='dac_review', interview_date=timezone.localdate())
    other_dac = make_user('dac2.cs@au.edu.pk', role=Role.DAC_MEMBER, dept=cs)
    act(client_for(other_dac), app_id, 'shortlist', percentage=50)
    assert titles(other_dac) == []


def test_returned_and_signed_letter_reach_the_student(cycle, cs, officer, django_capture_on_commit_callbacks):
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    student = Application.objects.get(pk=app_id).student
    officer.post(f'{REVIEW}{app_id}/flags/', {'section': 'income', 'note': 'Net pay missing.'}, format='json')
    act(officer, app_id, 'return', 'Please add the net pay.')
    last = Notification.objects.filter(recipient=student).first()
    assert last.title.endswith('was returned to you for corrections') and last.body == 'Please add the net pay.'

    Application.objects.filter(pk=app_id).update(status='vc_review', scholarship_percentage=50)
    with django_capture_on_commit_callbacks(execute=True):
        act(client_for(make_user('vc@au.edu.pk', role=Role.VICE_CHANCELLOR)), app_id, 'approve')
    response = officer.post(f'{REVIEW}{app_id}/award-letter/signed/',
                            {'signed_issued_on': timezone.localdate().isoformat()}, format='multipart')
    assert response.status_code == 200
    assert titles(student)[-1] == 'Your signed award letter is ready'
    assert student_api.get('/api/v1/notifications/').json()['unread'] == len(titles(student))
