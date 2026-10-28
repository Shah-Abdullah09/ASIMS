"""Page 7 "Mandatory Document Checklist": which upload slots apply to a given application.

Agreed rules: items 1, 2, 6, 9, 12 and 18 are always required (item 5, the income declaration,
is Form 2 and handled separately). Items 3, 4, 8, 10, 11, 13 and 16 become required from the
student's own answers. Items 7, 14, 15 and 17 are optional."""
from .choices import AccommodationStatus, DocumentSlot, LifeStatus, ParentRole, Profession, Relationship

DEFAULT_MAX_FILES = 5
MAX_FILES = {DocumentSlot.BANK_STATEMENTS: 6}  # six monthly statements (or one combined PDF)

ALWAYS = 'always'
CONDITIONAL = 'conditional'
OPTIONAL = 'optional'


def _salaried_parents(app):
    return [p for p in app.parents.all()
            if p.status == LifeStatus.ALIVE and p.profession in (Profession.EMPLOYED, Profession.RETIRED)]


def slot_rules(app):
    """slot -> (kind, required now?, reason shown to the student)."""
    salaried = bool(_salaried_parents(app))
    sibling_earns = any(m.relationship in (Relationship.BROTHER, Relationship.SISTER)
                        for m in app.earning_members.all())
    parent_deceased = any(p.role in (ParentRole.FATHER, ParentRole.MOTHER) and p.status == LifeStatus.DECEASED
                          for p in app.parents.all())
    always = (ALWAYS, True, 'Required for every applicant.')
    optional = (OPTIONAL, False, 'Optional. Upload if it applies to you.')

    def conditional(applies, because, otherwise):
        return (CONDITIONAL, applies, because if applies else otherwise)

    return {
        DocumentSlot.CNIC_COPIES: always,
        DocumentSlot.DOMICILE: always,
        DocumentSlot.SALARY_CERTIFICATE: conditional(
            salaried, 'Required because a parent or guardian is employed or retired.',
            'Required only if a parent or guardian is employed or retired.'),
        DocumentSlot.SALARY_SLIP: conditional(
            salaried, 'Required because a parent or guardian is employed or retired.',
            'Required only if a parent or guardian is employed or retired.'),
        DocumentSlot.BANK_STATEMENTS: always,
        DocumentSlot.OTHER_INCOME: optional,
        DocumentSlot.SIBLING_INCOME: conditional(
            sibling_earns, 'Required because you listed an earning brother or sister.',
            'Required only if a brother or sister earns.'),
        DocumentSlot.FEE_RECEIPTS: always,
        DocumentSlot.PREVIOUS_SCHOLARSHIPS: conditional(
            app.other_scholarships is True, 'Required because you said you received other scholarships.',
            'Required only if you received other scholarships.'),
        DocumentSlot.MEDICAL_BILLS: conditional(
            (app.medical_monthly or 0) > 0, 'Required because you entered medical expenditure.',
            'Required only if you enter medical expenditure.'),
        DocumentSlot.UTILITY_BILLS: always,
        DocumentSlot.RENT_AGREEMENT: conditional(
            app.accommodation_status == AccommodationStatus.RENTED, 'Required because your house is rented.',
            'Required only if your house is rented.'),
        DocumentSlot.HOSTEL_PROOF: optional,
        DocumentSlot.TRANSPORT_FEE: optional,
        DocumentSlot.DEATH_CERTIFICATE: conditional(
            parent_deceased, 'Required because a parent is marked as deceased.',
            'Required only if a parent is deceased.'),
        DocumentSlot.DIVORCE_CERTIFICATE: optional,
        DocumentSlot.RESULT_CARDS: always,
    }


def max_files(slot):
    return MAX_FILES.get(slot, DEFAULT_MAX_FILES)


def build_checklist(app, file_serializer):
    """One entry per slot, in checklist order, with its files and whether it is still missing."""
    rules = slot_rules(app)
    files_by_slot = {}
    for doc in app.documents.all():
        files_by_slot.setdefault(doc.slot, []).append(doc)
    checklist = []
    for slot in DocumentSlot:
        kind, required, reason = rules[slot]
        files = files_by_slot.get(slot, [])
        checklist.append({
            'slot': slot.value,
            'label': slot.label,
            'kind': kind,
            'required': required,
            'reason': reason,
            'max_files': max_files(slot),
            'files': file_serializer(files, many=True).data,
            'missing': required and not files,
        })
    return checklist


def missing_slots(app):
    rules = slot_rules(app)
    uploaded = set(app.documents.values_list('slot', flat=True))
    return [slot for slot in DocumentSlot if rules[slot][1] and slot.value not in uploaded]
