"""The award letter: an A4 PDF on the university letterhead, generated when the Vice Chancellor approves.

The text is the standard wording agreed for Phase 4."""
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib.units import mm

from apps.documents.pdf import Letter

from .models import AwardLetter

CONDITIONS = [
    'The grant covers {pct}% of the tuition fee of the {cycle} semester only. It does not cover admission, '
    'examination, hostel, transport or other charges.',
    'The Finance Office will adjust the grant in your semester fee voucher. No cash is paid.',
    'The grant may be withdrawn if any information or document you submitted is found to be incorrect, or if you '
    'leave the university, are suspended or do not meet the university\'s academic and discipline rules.',
    'A new application is needed for each semester or scholarship cycle.',
]


def render_award_letter(app, reference, issued_on, percentage):
    """The letter as PDF bytes."""
    student = app.student
    name = app.applicant_name or student.full_name
    letter = Letter(f'Award letter {reference}')
    letter.letterhead(reference, issued_on)
    letter.space(14 * mm)
    letter.title('AWARD LETTER', 'Need Based Financial Grant')
    letter.space(18 * mm)
    letter.details([('Name', name),
                    ('Registration ID', app.registration_id or student.registration_id or '-'),
                    ('Program', app.program or '-'),
                    ('Department', student.department.name if student.department else '-'),
                    ('Scholarship cycle', app.cycle.name),
                    ('Application number', str(app.pk))])
    letter.space(6 * mm)
    letter.paragraph(f'Dear {name},')
    letter.space(4)
    letter.paragraph(
        'We are pleased to inform you that, on the recommendation of the Departmental Admission Committee and with '
        'the approval of the Director, the Registrar and the Vice Chancellor, you have been awarded a need based '
        f'financial grant of {percentage}% of the semester tuition fee for the {app.cycle.name} semester.')
    letter.space(8)
    letter.heading('Conditions')
    letter.space(16)
    letter.numbered(condition.format(pct=percentage, cycle=app.cycle.name) for condition in CONDITIONS)
    letter.space(6)
    letter.paragraph('Congratulations, and we wish you success in your studies.')
    letter.space(26 * mm)
    letter.signature()
    return letter.finish('Valid when signed and stamped by the Placement Office.')


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
