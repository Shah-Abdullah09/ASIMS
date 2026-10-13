"""Form 2: the stamp-paper income declarations ("Template of Income Certificates F-26").

The university's wording below is reproduced exactly and must not be changed. Values the system
already knows are filled in; everything else is left as a blank line to be completed by hand.
The student's own details are shown separately, outside the official text."""
from django.db import transaction

from .choices import DeclarationTemplate, LandCategory

BLANK = '____________________'

STAMP_NOTE = 'This declaration of income statement must be printed on a stamp paper (having value ≥ Rs.100)'

CLOSING = ('I have knowingly and willfully stated the above facts for the purpose of securing Air University '
           'Need Based Financial Aid and if above stated facts are found wrong at any point in time during / '
           "after my child's academic life cycle: financial aid, admission, degree, awards should be cancelled.")

UNION_COUNCILLOR = {'title': 'Union Councillor', 'fields': ['Sign & Stamp', 'Name']}
GAZETTED_OFFICER = {'title': 'Govt. / Gazetted officer, BPS 17 or above', 'fields': ['Sign & Stamp', 'Name', 'Contact No']}


def _v(value):
    return BLANK if value in (None, '') else str(value)


def _rupees(value):
    return BLANK if value is None else f'{value:,}'


def _agricultural_land(app):
    return next((land for land in app.land_holdings.all() if land.category == LandCategory.AGRICULTURAL), None)


def _items(template, parent, app):
    if template == DeclarationTemplate.SELF_EMPLOYED:
        annual = parent.gross_monthly_income * 12 if parent.gross_monthly_income is not None else None
        return [
            f'1. I am a self-employed person and run the business of {BLANK}',
            f'2. The name of my business/shop is {_v(parent.employer)}',
            f'3. The address of my business/shop is {BLANK}',
            f'4. The business/shop location is owned by {BLANK}',
            f'5. I deal in the following main commodities {BLANK}',
            f'6. My total annual income from this business/shop is Rs. {_rupees(annual)}',
            f'7. I have {BLANK} number of hired workers.',
        ]
    if template == DeclarationTemplate.FARMER:
        land = _agricultural_land(app)
        return [
            f'1. I, along with all my family members, own {_v(land and land.size)} of agricultural land situated at '
            f'{_v(land and land.location)}',
            f'2. I cultivate {BLANK} crops on this land.',
            f'3. My annual income from the sale of the crop is Rs. {BLANK}',
            f'4. I have {BLANK} number of hired workers working on my land.',
        ]
    if template == DeclarationTemplate.LABOURER:
        return [
            '1. I work as a labourer/ private worker',
            f'2. My nature of work is {_v(parent.occupation_type)}.',
            f'3. My monthly income from all sources is Rs. {_rupees(parent.net_monthly_income)}.',
        ]
    return [  # employed or pensioner
        '1. I am a salaried/Retired person.',
        f'2. The name of my Department/organization is {_v(parent.employer)}',
        f'3. The address of Department/organization is {BLANK}',
        f'4. My Designation is {_v(parent.designation_grade)}',
        f'5. Department/organization location is owned by {BLANK}',
        f'6. My total Monthly income is Rs. {_rupees(parent.net_monthly_income)}',
    ]


NOTES = {
    DeclarationTemplate.SELF_EMPLOYED: f"{STAMP_NOTE} bearing the shop's/business' address and contact numbers.",
    DeclarationTemplate.FARMER: f'{STAMP_NOTE}.',
    DeclarationTemplate.LABOURER: f'{STAMP_NOTE}.',
    DeclarationTemplate.EMPLOYED: (f'{STAMP_NOTE}. bearing the address and contact numbers of the department / '
                                   'organization. A latest salary slip, duly signed by the head of department, '
                                   'must be attached with this declaration.'),
}

SIGNATURE_LINE = {
    DeclarationTemplate.SELF_EMPLOYED: 'Signature & Name business/Shop Owner          Date',
    DeclarationTemplate.FARMER: 'Signature & Name          Date',
    DeclarationTemplate.LABOURER: 'Signature & Name          Date',
    DeclarationTemplate.EMPLOYED: 'Signature:          Date:',
}


def render(declaration):
    """The printable declaration for one parent or guardian."""
    parent, app = declaration.parent, declaration.application
    template = DeclarationTemplate(declaration.template)
    person = parent.get_role_display().lower()
    countersign = ([dict(UNION_COUNCILLOR, fields=['Sign & Stamp', 'Name', 'Contact No']), GAZETTED_OFFICER]
                   if template == DeclarationTemplate.EMPLOYED else [UNION_COUNCILLOR, GAZETTED_OFFICER])
    return {
        'template': template.value,
        'title': template.label,
        'note': NOTES[template],
        'header': f'I, {_v(parent.name)} bearing CNIC # {_v(parent.cnic)} hereby, truthfully state the following:',
        'items': _items(template, parent, app),
        'closing': CLOSING,
        'signature_line': SIGNATURE_LINE[template],
        'countersigned_by': countersign,
        # Shown on the printable page but outside the official text
        'student_reference': {
            'student_name': app.applicant_name,
            'registration_id': app.registration_id,
            'application_no': app.pk,
        },
        'instructions': [
            'Copy or print the text above onto stamp paper worth Rs.100 or more.',
            f'Your {person} ({_v(parent.name)}) completes any blank lines, then signs and dates it.',
            'Get it countersigned and stamped by a Union Councillor and by a Government / Gazetted officer '
            '(BPS 17 or above).',
            'Scan or photograph the completed stamp paper and upload it here (PDF, JPG or PNG, up to 5 MB).',
            f'Hand the original stamp paper to the Placement Office, quoting application number {app.pk}.',
        ],
    }


def sync_declarations(app):
    """Keep one declaration per living, earning parent or guardian.

    Removes declarations for people who no longer need one, and clears a scan that was made from a
    different template (e.g. the profession was changed after printing)."""
    from .models import Declaration, ParentGuardian  # avoid a circular import

    # query fresh rows: the caller's application may hold a prefetched (pre-save) parent list
    parents = ParentGuardian.objects.filter(application=app)
    needed = {p.pk: p.declaration_template for p in parents if p.declaration_template}
    stale_files = []
    for declaration in Declaration.objects.filter(application=app):
        template = needed.pop(declaration.parent_id, None)
        if template is None:
            if declaration.scan:
                stale_files.append((declaration.scan.storage, declaration.scan.name))
            declaration.delete()
        elif declaration.template != template:
            if declaration.scan:
                stale_files.append((declaration.scan.storage, declaration.scan.name))
            declaration.template = template
            declaration.scan = None
            declaration.scan_original_name = declaration.scan_content_type = ''
            declaration.scan_size = declaration.scan_uploaded_at = declaration.scan_uploaded_by = None
            declaration.save()
    for parent_id, template in needed.items():
        Declaration.objects.create(application=app, parent_id=parent_id, template=template)
    for storage, name in stale_files:
        transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
