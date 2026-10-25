"""Rules checked when a student submits. Drafts may be incomplete; a submission may not.

Problems are grouped by wizard section so the form can send the student to the right step."""
import re

from .calculations import summarize
from .checklist import missing_slots
from .choices import AccommodationStatus, AssetIncomeSource, EducationLevel, LifeStatus, ParentRole, Profession

REQUIRED = 'This field is required.'
MIN_STATEMENT = 100
MIN_EXPLANATION = 20


def _missing(obj, fields):
    return {f: [REQUIRED] for f in fields if getattr(obj, f) in (None, '')}


def _personal(app):
    return _missing(app, ['registration_id', 'program', 'applicant_name', 'gender', 'marital_status', 'cnic',
                          'date_of_birth', 'domicile', 'present_address', 'permanent_address', 'mobile'])


def _household(app):
    errors = _missing(app, ['total_family_members'])
    if not app.household_members.exists():
        errors['household_members'] = ['List the family members who live with you.']
    return errors


def _parent_errors(parent, guardian=False):
    errors = _missing(parent, ['name', 'cnic', 'status'])
    if guardian:
        errors.update(_missing(parent, ['relationship_to_applicant']))
    if parent.status == LifeStatus.ALIVE:
        errors.update(_missing(parent, ['profession']))
        if parent.profession and parent.profession != Profession.NOT_EARNING:
            errors.update(_missing(parent, ['gross_monthly_income', 'net_monthly_income']))
        if parent.profession == Profession.EMPLOYED:
            errors.update(_missing(parent, ['employer', 'occupation_type']))
    return errors


def _parents(app):
    by_role = {p.role: p for p in app.parents.all()}
    errors = {}
    father, mother, guardian = (by_role.get(r) for r in (ParentRole.FATHER, ParentRole.MOTHER, ParentRole.GUARDIAN))
    if father is None:
        errors['father'] = ["Enter your father's details."]
    elif e := _parent_errors(father):
        errors['father'] = e
    if mother is None:
        errors['mother'] = ["Enter your mother's details."]
    elif e := _parent_errors(mother):
        errors['mother'] = e
    if father and father.status == LifeStatus.DECEASED and guardian is None:
        errors['guardian'] = ['A guardian is required because your father is deceased.']
    elif guardian and (e := _parent_errors(guardian, guardian=True)):
        errors['guardian'] = e
    return errors


def _income(app):
    errors = _missing(app, ['applicant_gross_income', 'applicant_net_income'])
    members = list(app.earning_members.all())
    if any(m.net_pay is None for m in members):
        errors['earning_members'] = ['Enter the net (take-home) pay for every earning member.']
    listed = {m.relationship for m in members}
    for parent in app.parents.all():
        if parent.status == LifeStatus.ALIVE and (parent.gross_monthly_income or 0) > 0 and parent.role not in listed:
            errors.setdefault('earning_members', []).append(
                f"Your {parent.get_role_display().lower()}'s income must also be listed under earning family members.")
    other = next((r for r in app.asset_income.all() if r.source == AssetIncomeSource.OTHER), None)
    if other and other.total > 0 and not app.asset_income_other_specify:
        errors['asset_income_other_specify'] = ['Say what the "Other" asset income is.']
    return errors


def _accommodation(app):
    errors = _missing(app, ['accommodation_type', 'accommodation_status', 'plot_size_sqft', 'covered_area_sqft',
                            'accommodation_address', 'bedrooms', 'air_conditioners', 'other_house_owned'])
    if app.accommodation_status == AccommodationStatus.RENTED:
        errors.update(_missing(app, ['rent_paid_by', 'monthly_rent']))
    if app.other_house_owned:
        errors.update(_missing(app, ['other_house_details']))
    return errors


def _expenses(app):
    errors = _missing(app, ['medical_monthly', 'misc_monthly'])
    if app.utility_months.count() < 3:
        errors['utility_months'] = ['Enter the utility bills for each of the last three months.']
    summary = summarize(app)
    if summary['net_monthly_disposable'] < 0 and len(app.negative_income_explanation.strip()) < MIN_EXPLANATION:
        errors['negative_income_explanation'] = [
            'Your expenditure is more than your income. Explain how the gap is met (at least 20 characters).']
    return errors


def _assets(app):
    errors = _missing(app, ['owns_transport', 'cattle_count', 'education_loan', 'admission_fee_paid_how'])
    if app.owns_transport and not app.vehicles.exists():
        errors['vehicles'] = ['Add the vehicles your family owns.']
    if app.education_loan:
        errors.update(_missing(app, ['education_loan_details']))
    return errors


def _education(app):
    errors = _missing(app, ['last_institution_monthly_fee', 'other_scholarships'])
    levels = {r.level for r in app.education_records.all()}
    for level in (EducationLevel.SECONDARY, EducationLevel.INTERMEDIATE):
        if level not in levels:
            errors.setdefault('education_records', []).append(f'Enter your {level.label} record.')
    if app.other_scholarships and not app.previous_scholarships.exists():
        errors['previous_scholarships'] = ['Add the scholarships you received.']
    if len(app.statement_of_purpose.strip()) < MIN_STATEMENT:
        errors['statement_of_purpose'] = [f'Write at least {MIN_STATEMENT} characters.']
    return errors


def _normalise(name):
    return re.sub(r'\s+', ' ', name or '').strip().lower()


def _undertaking(app):
    errors = {}
    if not app.undertaking_accepted:
        errors['undertaking_accepted'] = ['You must accept the undertaking.']
    if not app.undertaking_name.strip():
        errors['undertaking_name'] = ['Type your full name.']
    elif _normalise(app.undertaking_name) != _normalise(app.applicant_name):
        errors['undertaking_name'] = ['Type your name exactly as entered in your personal details.']
    return errors


CHECKS = [('personal', _personal), ('household', _household), ('parents', _parents), ('income', _income),
          ('accommodation', _accommodation), ('expenses', _expenses), ('assets', _assets),
          ('education', _education), ('undertaking', _undertaking)]


def readiness(app):
    """Everything still stopping this application from being submitted."""
    sections = {name: errors for name, check in CHECKS if (errors := check(app))}
    documents = [slot.value for slot in missing_slots(app)]
    problems = []
    if not app.cycle.is_open():
        problems.append(f'The {app.cycle.name} cycle is closed for applications.')
    return {
        'ready': not sections and not documents and not problems,
        'sections': sections,
        'missing_documents': documents,
        'problems': problems,
    }


def completion(app):
    """The three things that make an application complete, shown to the student."""
    declarations = list(app.declarations.all())
    submitted = app.submitted_at is not None
    return {
        'form_submitted': submitted,
        'declarations_required': len(declarations),
        'scans_uploaded': all(bool(d.scan) for d in declarations),
        'physical_copies_received': all(d.physical_received_on is not None for d in declarations),
        'complete': submitted and all(d.is_complete for d in declarations),
    }
