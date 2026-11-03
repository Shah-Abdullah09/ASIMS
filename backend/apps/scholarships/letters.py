"""The award letter: an A4 PDF with the university letterhead, generated when the Vice Chancellor approves.

The text is the standard wording agreed for Phase 4; the signature block is left blank for a manual signature
and the office stamp (no e-signature)."""
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from .models import AwardLetter

LOGO = Path(__file__).parent / 'assets' / 'au-logo.png'
BLUE = HexColor('#1A6FA0')
TEXT = HexColor('#1A1A1A')

CONDITIONS = [
    'The grant covers {pct}% of the tuition fee of the {cycle} semester only. It does not cover admission, '
    'examination, hostel, transport or other charges.',
    'The Finance Office will adjust the grant in your semester fee voucher. No cash is paid.',
    'The grant may be withdrawn if any information or document you submitted is found to be incorrect, or if you '
    'leave the university, are suspended or do not meet the university\'s academic and discipline rules.',
    'A new application is needed for each semester or scholarship cycle.',
]


def _paragraph(pdf, text, x, y, width, font='Helvetica', size=11, leading=15):
    for line in simpleSplit(text, font, size, width):
        pdf.setFont(font, size)
        pdf.drawString(x, y, line)
        y -= leading
    return y


def render_award_letter(app, reference, issued_on, percentage):
    """The letter as PDF bytes."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle(f'Award letter {reference}')
    pdf.setAuthor('Placement Office, Air University Multan')
    page_w, page_h = A4
    left, right = 25 * mm, page_w - 25 * mm
    width = right - left

    # Letterhead
    top = page_h - 20 * mm
    logo_h = 22 * mm
    if LOGO.exists():
        logo = ImageReader(str(LOGO))
        iw, ih = logo.getSize()
        pdf.drawImage(logo, left, top - logo_h, width=logo_h * iw / ih, height=logo_h, mask='auto')
    pdf.setFillColor(BLUE)
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawRightString(right, top - 8 * mm, 'AIR UNIVERSITY MULTAN')
    pdf.setFont('Helvetica', 11)
    pdf.drawRightString(right, top - 14 * mm, 'Placement Office')
    pdf.setStrokeColor(BLUE)
    pdf.setLineWidth(1.2)
    pdf.line(left, top - logo_h - 4 * mm, right, top - logo_h - 4 * mm)

    pdf.setFillColor(TEXT)
    y = top - logo_h - 14 * mm
    pdf.setFont('Helvetica', 10)
    pdf.drawString(left, y, f'Ref: {reference}')
    pdf.drawRightString(right, y, f'Date: {issued_on:%d %B %Y}')

    y -= 14 * mm
    pdf.setFont('Helvetica-Bold', 13)
    pdf.drawCentredString(page_w / 2, y, 'AWARD LETTER')
    pdf.setFont('Helvetica', 11)
    pdf.drawCentredString(page_w / 2, y - 6 * mm, 'Need Based Financial Grant')

    y -= 18 * mm
    student = app.student
    details = [('Name', app.applicant_name or student.full_name),
               ('Registration ID', app.registration_id or student.registration_id or '-'),
               ('Program', app.program or '-'),
               ('Department', student.department.name if student.department else '-'),
               ('Scholarship cycle', app.cycle.name),
               ('Application number', str(app.pk))]
    for label, value in details:
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawString(left, y, f'{label}:')
        pdf.setFont('Helvetica', 11)
        pdf.drawString(left + 45 * mm, y, value)
        y -= 6.5 * mm

    y -= 6 * mm
    y = _paragraph(pdf, f'Dear {app.applicant_name or student.full_name},', left, y, width)
    y -= 4
    y = _paragraph(pdf, (
        'We are pleased to inform you that, on the recommendation of the Departmental Admission Committee and with '
        'the approval of the Director, the Registrar and the Vice Chancellor, you have been awarded a need based '
        f'financial grant of {percentage}% of the semester tuition fee for the {app.cycle.name} semester.'),
        left, y, width)
    y -= 8
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(left, y, 'Conditions')
    y -= 16
    for number, condition in enumerate(CONDITIONS, 1):
        text = condition.format(pct=percentage, cycle=app.cycle.name)
        pdf.setFont('Helvetica', 11)
        pdf.drawString(left, y, f'{number}.')
        y = _paragraph(pdf, text, left + 6 * mm, y, width - 6 * mm) - 3
    y -= 6
    y = _paragraph(pdf, 'Congratulations, and we wish you success in your studies.', left, y, width)

    # Signature block: signed and stamped by hand
    y -= 26 * mm
    pdf.line(right - 70 * mm, y, right, y)
    pdf.setFont('Helvetica', 10)
    pdf.drawString(right - 70 * mm, y - 5 * mm, 'Placement Office')
    pdf.drawString(right - 70 * mm, y - 10 * mm, 'Air University Multan')
    pdf.drawString(left, y - 5 * mm, 'Office stamp:')

    pdf.setFont('Helvetica', 8)
    pdf.setFillColor(HexColor('#555555'))
    pdf.drawCentredString(page_w / 2, 12 * mm, f'Generated by ASIMS on {timezone.localtime():%d %b %Y %H:%M}. '
                                                'Valid when signed and stamped by the Placement Office.')
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def issue_award_letter(app):
    """Create (or recreate) the application's award letter from its approved percentage."""
    issued_on = timezone.localdate()
    reference = AwardLetter.reference_for(app)
    content = render_award_letter(app, reference, issued_on, app.scholarship_percentage)
    letter = AwardLetter.objects.filter(application=app).first() or AwardLetter(application=app)
    old = (letter.pdf.storage, letter.pdf.name) if letter.pk and letter.pdf else None
    letter.reference, letter.issued_on, letter.percentage = reference, issued_on, app.scholarship_percentage
    letter.pdf.save('award-letter.pdf', ContentFile(content), save=False)
    letter.save()
    if old:
        old[0].delete(old[1])
    return letter
