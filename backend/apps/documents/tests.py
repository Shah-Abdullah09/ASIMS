"""Reading documents for the automatic check (PDF text layer, OCR of images, missing engine)."""
from io import BytesIO

import pytest
import pytesseract
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db.models import FileField
from django.db.models.fields.files import FieldFile
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas

from . import ocr


def stored(tmp_path, name, content):
    storage = FileSystemStorage(location=tmp_path)
    return FieldFile(None, FileField(storage=storage), storage.save(name, ContentFile(content)))


def pdf_with_text(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()


def png():
    buffer = BytesIO()
    Image.new('RGB', (60, 20), 'white').save(buffer, 'PNG')
    return buffer.getvalue()


def test_pdf_text_layer_is_read(tmp_path):
    f = stored(tmp_path, 'cnic.pdf', pdf_with_text('CNIC 36302-1234567-1 Ali Khan'))
    reading = ocr.read_text(f, 'application/pdf')
    assert reading.status == ocr.READ and '36302-1234567-1' in reading.text


def test_pdf_without_text_and_damaged_files(tmp_path):
    empty = stored(tmp_path, 'scan.pdf', pdf_with_text(''))
    assert ocr.read_text(empty, 'application/pdf').status == ocr.NO_TEXT
    broken = stored(tmp_path, 'broken.pdf', b'%PDF-1.4 not really')
    assert ocr.read_text(broken, 'application/pdf').status in (ocr.FAILED, ocr.NO_TEXT)


def test_images_without_the_engine_are_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, 'engine_available', lambda: False)
    assert ocr.read_text(stored(tmp_path, 'cnic.png', png()), 'image/png').status == ocr.UNAVAILABLE


def test_images_are_read_by_the_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, 'engine_available', lambda: True)
    monkeypatch.setattr(pytesseract, 'image_to_string', lambda image, lang: ' Net pay 72,000 \n')
    reading = ocr.read_text(stored(tmp_path, 'slip.png', png()), 'image/png')
    assert reading.status == ocr.READ and reading.text == 'Net pay 72,000'


@pytest.mark.skipif(not ocr.engine_available(), reason='Tesseract is not installed on this machine')
def test_real_tesseract_reads_printed_digits(tmp_path):
    image = Image.new('RGB', (900, 120), 'white')
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 48)
    except OSError:
        font = ImageFont.load_default(size=48)
    ImageDraw.Draw(image).text((20, 30), 'CNIC 36302-1234567-1', fill='black', font=font)
    buffer = BytesIO()
    image.save(buffer, 'PNG')
    reading = ocr.read_text(stored(tmp_path, 'cnic.png', buffer.getvalue()), 'image/png')
    assert reading.status == ocr.READ and '36302' in reading.text.replace(' ', '')
