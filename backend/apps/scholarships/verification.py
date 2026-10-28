"""Placement verification: per-file review, section flags, and what a returned application unlocks.

While a case is "Returned to student" only the flagged sections and the document slots that need work
can be changed: a slot with a file marked "Needs clarification", or a required slot left empty after the
student changed an answer. Verified files stay locked."""
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .checklist import slot_rules, missing_slots
from .choices import ApplicationStatus, DocumentReview, DocumentSlot
from .models import SectionFlag
from .submission import completion


def open_flags(app):
    return app.flags.filter(resolved_at__isnull=True)


def unlocked(app):
    """What the student may change now: {'sections': [...], 'slots': [...]}. Drafts are fully open."""
    if app.status == ApplicationStatus.DRAFT:
        return {'sections': None, 'slots': None}  # None = everything
    if app.status != ApplicationStatus.RETURNED:
        return {'sections': [], 'slots': []}
    sections = sorted(set(open_flags(app).values_list('section', flat=True)))
    returned_at = (app.status_history.filter(to_status=ApplicationStatus.RETURNED)
                   .order_by('-changed_at').values_list('changed_at', flat=True).first())
    # A slot stays open for this return once the student has started fixing it (the new file is unreviewed)
    changed = Q(uploaded_at__gte=returned_at) if returned_at else Q(pk__in=[])
    slots = set(app.documents.filter(Q(review_status=DocumentReview.NEEDS_CLARIFICATION) | changed)
                .values_list('slot', flat=True))
    slots |= {slot.value for slot in missing_slots(app)}
    return {'sections': sections, 'slots': [s.value for s in DocumentSlot if s.value in slots]}


def section_unlocked(app, section):
    allowed = unlocked(app)['sections']
    return allowed is None or section in allowed


def slot_unlocked(app, slot):
    allowed = unlocked(app)['slots']
    return allowed is None or slot in allowed


def completion_problem(app):
    """Form 2 must be complete (scans uploaded, originals received) before the case leaves Placement."""
    state = completion(app)
    if state['complete']:
        return None
    missing = [label for key, label in (('scans_uploaded', 'Form 2 scan(s)'),
                                        ('physical_copies_received', 'original stamp paper(s)'))
               if not state[key]]
    return f'The application is not complete yet. Missing: {", ".join(missing)}.'


def check_returnable(app):
    """Returning needs something for the student to fix."""
    if not open_flags(app).exists() and not app.documents.filter(
            review_status=DocumentReview.NEEDS_CLARIFICATION).exists():
        raise ValidationError({'action': 'Flag at least one section or mark at least one document as '
                                         '"Needs clarification" before returning the application.'})


def verification_problems(app):
    """What still stops Placement from verifying the case (empty when it can go to the DAC)."""
    problems = []
    rules = slot_rules(app)
    docs = list(app.documents.all())
    unclear = [d for d in docs if d.review_status == DocumentReview.NEEDS_CLARIFICATION]
    unchecked = [d for d in docs if rules[d.slot][1] and d.review_status != DocumentReview.VERIFIED
                 and d not in unclear]
    if unclear:
        problems.append(f'{len(unclear)} document(s) still need clarification.')
    if unchecked:
        problems.append(f'{len(unchecked)} required document(s) not verified yet.')
    if missing := missing_slots(app):
        problems.append(f'{len(missing)} required document slot(s) are empty.')
    if (flags := open_flags(app).count()):
        problems.append(f'{flags} flagged section(s) still open; clear them first.')
    if problem := completion_problem(app):
        problems.append(problem)
    return problems


def check_verifiable(app):
    if problems := verification_problems(app):
        raise ValidationError({'action': ['The case cannot be verified yet.', *problems]})


def resolve_flags(app, user):
    """On resubmission every open flag counts as answered; Placement checks again and may flag anew."""
    open_flags(app).update(resolved_at=timezone.now(), resolved_by=user, resolution=SectionFlag.FIXED_BY_STUDENT)

