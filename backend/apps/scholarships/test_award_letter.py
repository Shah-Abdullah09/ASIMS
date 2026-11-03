"""The award letter: generated on VC approval, downloaded by the student, signed copy recorded by Placement."""
from datetime import timedelta
from io import BytesIO

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditLog

from .models import Application, AwardLetter
from .test_review import (REVIEW, STUDENT_BASE, act, client_for, cs, cycle, make_user, officer,  # noqa: F401
                          submitted_application, temp_media)
from .test_submission import PDF

def png_bytes():
    buffer = BytesIO()
    Image.new('RGB', (40, 20), 'white').save(buffer, 'PNG')
    return buffer.getvalue()


PNG = png_bytes()


def body(response):
    return b''.join(response.streaming_content)


@pytest.fixture
def approved(cycle, cs, django_capture_on_commit_callbacks):
    """(student client, id) of a CS case the VC has just approved at 60%."""
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    Application.objects.filter(pk=app_id).update(status='vc_review', scholarship_percentage=60, program='BS CS')
    vc = client_for(make_user('vc@au.edu.pk', role=Role.VICE_CHANCELLOR, name='VC'))
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert act(vc, app_id, 'approve').status_code == 200
    return student_api, app_id


def letter_url(app_id, generated=False):
    return f'/api/v1/scholarships/award-letters/{app_id}/' + ('?version=generated' if generated else '')


def sign(client, app_id, on=None, file=None):
    data = {'signed_issued_on': (on or timezone.localdate()).isoformat()}
    if file:
        data['file'] = file
    return client.post(f'{REVIEW}{app_id}/award-letter/signed/', data, format='multipart')


def test_vc_approval_generates_the_letter(approved):
    _, app_id = approved
    letter = AwardLetter.objects.get(application_id=app_id)
    assert letter.reference == f'ASIMS/NBFG/Fall-26/{app_id:04d}' and letter.percentage == 60
    assert letter.issued_on == timezone.localdate()
    with letter.pdf.open('rb') as f:
        content = f.read()
    assert content.startswith(b'%PDF') and len(content) > 2000  # includes the logo
    entry = AuditLog.objects.get(action=AuditAction.AWARD_LETTER_GENERATED)
    assert entry.actor_role == 'vice_chancellor' and entry.details['reference'] == letter.reference


def test_approval_email_mentions_the_letter(approved):
    _, app_id = approved
    (message,) = mail.outbox
    assert f'ASIMS/NBFG/Fall-26/{app_id:04d}' in message.body and 'award letter' in message.body


def test_no_letter_before_the_vc_approves(cycle, cs):
    student_api, app_id = submitted_application(cycle, cs, 'ali@gmail.com')
    assert student_api.get(f'{STUDENT_BASE}{app_id}/').json()['award_letter'] is None
    assert student_api.get(letter_url(app_id)).status_code == 404


def test_student_and_placement_download_others_cannot(approved, officer, cs):
    student_api, app_id = approved
    info = student_api.get(f'{STUDENT_BASE}{app_id}/').json()['award_letter']
    assert info['download_url'] == letter_url(app_id) and info['signed_copy'] is False
    assert 'generated_url' not in info
    response = student_api.get(letter_url(app_id))
    assert response.status_code == 200 and response['Content-Type'] == 'application/pdf'
    assert body(response).startswith(b'%PDF')
    assert officer.get(letter_url(app_id)).status_code == 200
    for who in [make_user('other@gmail.com', dept=cs), make_user('dac@au.edu.pk', role=Role.DAC_MEMBER, dept=cs)]:
        assert client_for(who).get(letter_url(app_id)).status_code == 404


def test_placement_records_the_signed_letter_and_the_student_gets_the_scan(approved, officer):
    student_api, app_id = approved
    response = sign(officer, app_id)
    assert response.status_code == 200
    info = response.json()['award_letter']
    assert info['signed_issued_on'] == timezone.localdate().isoformat() and info['signed_copy'] is False
    assert body(student_api.get(letter_url(app_id))).startswith(b'%PDF')  # still the generated letter

    response = sign(officer, app_id, file=SimpleUploadedFile('signed letter.png', PNG))
    assert response.status_code == 200 and response.json()['award_letter']['signed_copy'] is True
    assert response.json()['award_letter']['signed_scan_name'] == 'signed letter.png'
    assert body(student_api.get(letter_url(app_id))).startswith(b'\x89PNG')
    assert body(student_api.get(letter_url(app_id, generated=True))).startswith(b'\x89PNG')  # students get the signed one
    assert body(officer.get(letter_url(app_id, generated=True))).startswith(b'%PDF')
    assert student_api.get(f'{STUDENT_BASE}{app_id}/').json()['award_letter']['signed_copy'] is True
    assert AuditLog.objects.filter(action=AuditAction.SIGNED_LETTER_ISSUED).count() == 2


def test_signed_letter_checks(approved, officer, cs, cycle):
    student_api, app_id = approved
    assert sign(officer, app_id, on=timezone.localdate() + timedelta(days=1)).status_code == 400
    assert sign(officer, app_id, on=timezone.localdate() - timedelta(days=1)).status_code == 400  # before generation
    bad = sign(officer, app_id, file=SimpleUploadedFile('letter.pdf', b'MZ not a pdf'))
    assert bad.status_code == 400 and 'file' in bad.json()
    assert sign(student_api, app_id).status_code == 403
    _, early = submitted_application(cycle, cs, 'sara@gmail.com', 'Sara Ahmed', '2335901', '36302-7654321-2')
    assert sign(officer, early).status_code == 400  # no letter yet
    assert PDF  # the PDF fixture used by other tests is unchanged
