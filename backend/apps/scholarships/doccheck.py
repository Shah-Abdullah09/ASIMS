"""The automatic document check: read the CNIC copies and the salary documents and compare what they say with
the application form. Advisory only: it never blocks a decision, and automatic reading can miss text."""
import re

from apps.documents.ocr import NO_TEXT, READ, UNAVAILABLE, read_text

from .choices import DocumentSlot, LifeStatus, Profession

CNIC_RE = re.compile(r'(?<!\d)(\d{5})[\s\-.]?(\d{7})[\s\-.]?(\d)(?!\d)')
AMOUNT_RE = re.compile(r'(?<![\d,])(\d{1,3}(?:,\d{3})+|\d{4,})(?![\d,])')
CHECKED_SLOTS = (DocumentSlot.CNIC_COPIES, DocumentSlot.SALARY_CERTIFICATE, DocumentSlot.SALARY_SLIP)
SALARIED = (Profession.EMPLOYED, Profession.RETIRED)


def find_cnics(text):
    """Every CNIC-shaped number in the text, written 12345-1234567-1."""
    return {f'{a}-{b}-{c}' for a, b, c in CNIC_RE.findall(text)}


def find_amounts(text):
    """Every number of four or more digits (with or without thousands commas) as an integer."""
    return {int(m.replace(',', '')) for m in AMOUNT_RE.findall(text)}


def _words(text):
    return set(re.findall(r'[a-z]{2,}', text.lower()))


def name_found(name, text):
    """True when every word of the name (two letters or more) appears in the text."""
    wanted = _words(name)
    return bool(wanted) and wanted <= _words(text)


def _item(kind, label, expected, found, slot):
    return {'kind': kind, 'label': label, 'expected': expected, 'found': found, 'slot': slot}


def run_document_check(app):
    """Read the checked documents and compare them with the form. Returns (files, items).

    files: one row per document read, with its status. items: one row per comparison; found is True, False, or
    None when nothing in that slot could be read."""
    files, texts = [], {slot: [] for slot in CHECKED_SLOTS}
    for doc in app.documents.filter(slot__in=CHECKED_SLOTS).order_by('slot', 'pk'):
        reading = read_text(doc.file, doc.content_type)
        files.append({'document': doc.pk, 'slot': doc.slot, 'name': doc.original_name, 'status': reading.status})
        if reading.status == READ:
            texts[doc.slot].append(reading.text)

    def combined(*slots):
        parts = [t for s in slots for t in texts[s]]
        return '\n'.join(parts) if parts else None

    items = []
    cnic_text = combined(DocumentSlot.CNIC_COPIES)
    found_cnics = find_cnics(cnic_text) if cnic_text else set()
    people = [('Applicant', app.applicant_name, app.cnic)]
    people += [(p.get_role_display(), p.name, p.cnic) for p in app.parents.all()]
    for who, _, cnic in people:
        if cnic:
            items.append(_item('cnic', f"{who}'s CNIC", cnic, None if cnic_text is None else cnic in found_cnics,
                               DocumentSlot.CNIC_COPIES))
    if app.applicant_name:
        items.append(_item('name', "Applicant's name on the CNIC copies", app.applicant_name,
                           None if cnic_text is None else name_found(app.applicant_name, cnic_text),
                           DocumentSlot.CNIC_COPIES))

    salary_text = combined(DocumentSlot.SALARY_CERTIFICATE, DocumentSlot.SALARY_SLIP)
    amounts = find_amounts(salary_text) if salary_text else set()
    for parent in app.parents.all():
        if parent.status != LifeStatus.ALIVE or parent.profession not in SALARIED:
            continue
        declared = [v for v in (parent.net_monthly_income, parent.gross_monthly_income) if v]
        if declared:
            label = f"{parent.get_role_display()}'s salary (gross or net)"
            expected = ' or '.join(f'Rs {v:,}' for v in declared)
            items.append(_item('salary', label, expected,
                               None if salary_text is None else any(v in amounts for v in declared),
                               DocumentSlot.SALARY_SLIP))
    return files, items


def summary(files, items):
    """Counts for the screen: how many matched, how many need a look, and whether the engine was missing."""
    return {'matched': sum(1 for i in items if i['found'] is True),
            'not_found': sum(1 for i in items if i['found'] is False),
            'unreadable': sum(1 for i in items if i['found'] is None),
            'engine_missing': any(f['status'] == UNAVAILABLE for f in files),
            'no_text': sum(1 for f in files if f['status'] == NO_TEXT)}

