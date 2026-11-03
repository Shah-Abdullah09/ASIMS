"""The automatic document check: finding CNICs, names and salaries and comparing them with the form."""
import pytest
from django.core.files.base import ContentFile

from apps.documents import ocr
from apps.documents.tests import pdf_with_text

from .doccheck import find_amounts, find_cnics, name_found, run_document_check, summary
from .models import Application, ApplicationDocument
from .test_review import cs, cycle, submitted_application, temp_media  # noqa: F401


@pytest.mark.parametrize('text,cnics', [
    ('CNIC No. 36302-1234567-1', {'36302-1234567-1'}),
    ('3630212345671 and 36302 2222222 2', {'36302-1234567-1', '36302-2222222-2'}),
    ('phone 0300-1234567 and 123456789012345', set()),
])
def test_find_cnics(text, cnics):
    assert find_cnics(text) == cnics


def test_find_amounts():
    assert find_amounts('Gross Rs. 80,000/- Net 72000 Grade 15 year 2026') == {80000, 72000, 2026}


def test_name_found_needs_every_word():
    assert name_found('Ali Khan', 'NAME: ALI  KHAN\nFather: Aslam')
    assert not name_found('Ali Raza Khan', 'NAME: ALI KHAN')
    assert not name_found('', 'anything')


def replace_with_pdf(app_id, slot, text):
    """Swap the uploaded file of a slot for a PDF that contains `text`."""
    doc = ApplicationDocument.objects.filter(application_id=app_id, slot=slot).first()
    doc.file.save('doc.pdf', ContentFile(pdf_with_text(text)), save=False)
    doc.content_type = 'application/pdf'
    doc.save()


def test_check_compares_the_documents_with_the_form(cycle, cs):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')  # father 36302-1111111-1, net 72,000
    replace_with_pdf(app_id, 'cnic_copies', 'ALI KHAN 36302-1234567-1 MUHAMMAD ASLAM 36302-1111111-1')
    replace_with_pdf(app_id, 'salary_slip', 'Net salary Rs. 72,000 for October')
    app = Application.objects.get(pk=app_id)
    files, items = run_document_check(app)
    found = {i['label']: i['found'] for i in items}
    assert found["Applicant's CNIC"] is True and found["Father's CNIC"] is True
    assert found["Mother's CNIC"] is False  # not on the copies uploaded
    assert found["Applicant's name on the CNIC copies"] is True
    assert found["Father's salary (gross or net)"] is True
    assert {f['slot']: f['status'] for f in files}['cnic_copies'] == ocr.READ
    assert summary(files, items)['not_found'] == 1


def test_unreadable_documents_give_no_verdict(cycle, cs, monkeypatch):
    _, app_id = submitted_application(cycle, cs, 'ali@gmail.com')  # uploads are minimal PDFs without text
    monkeypatch.setattr(ocr, 'engine_available', lambda: False)
    files, items = run_document_check(Application.objects.get(pk=app_id))
    assert items and all(i['found'] is None for i in items)
    assert all(f['status'] in (ocr.NO_TEXT, ocr.FAILED) for f in files)
