"""Fixed option lists taken from the AU Need Based Financial Grant form."""
from django.db import models


class ApplicationStatus(models.TextChoices):
    """The stage of the approval chain an application is at (see workflow.py for who moves it on)."""
    DRAFT = 'draft', 'Draft'
    PLACEMENT_VERIFICATION = 'placement_verification', 'Placement verification'
    RETURNED = 'returned', 'Returned to student'
    DAC_REVIEW = 'dac_review', 'DAC review'
    AWAITING_FORWARDING = 'awaiting_forwarding', 'Awaiting forwarding'
    DIRECTOR_REVIEW = 'director_review', 'Director review'
    REGISTRAR_REVIEW = 'registrar_review', 'Registrar review'
    VC_REVIEW = 'vc_review', 'VC review'
    AWAITING_FEE_ADJUSTMENT = 'awaiting_fee_adjustment', 'Awaiting fee adjustment'
    REJECTED = 'rejected', 'Rejected'


class Gender(models.TextChoices):
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'


class MaritalStatus(models.TextChoices):
    SINGLE = 'single', 'Single'
    MARRIED = 'married', 'Married'
    WIDOWED = 'widowed', 'Widowed'
    DIVORCED = 'divorced', 'Divorced'


class Relationship(models.TextChoices):
    FATHER = 'father', 'Father'
    MOTHER = 'mother', 'Mother'
    BROTHER = 'brother', 'Brother'
    SISTER = 'sister', 'Sister'
    SPOUSE = 'spouse', 'Spouse'
    SON = 'son', 'Son'
    DAUGHTER = 'daughter', 'Daughter'
    GRANDPARENT = 'grandparent', 'Grandparent'
    GUARDIAN = 'guardian', 'Guardian'
    OTHER = 'other', 'Other'


class ParentRole(models.TextChoices):
    FATHER = 'father', 'Father'
    MOTHER = 'mother', 'Mother'
    GUARDIAN = 'guardian', 'Guardian'


class LifeStatus(models.TextChoices):
    ALIVE = 'alive', 'Alive'
    DECEASED = 'deceased', 'Deceased'


class Profession(models.TextChoices):
    EMPLOYED = 'employed', 'Employed'
    RETIRED = 'retired', 'Retired / Pensioner'
    BUSINESS = 'business', 'Business / Self-employed / Freelance'
    FARMER = 'farmer', 'Farmer'
    LABOURER = 'labourer', 'Labourer / Private worker'
    NOT_EARNING = 'not_earning', 'Not earning'


class DeclarationTemplate(models.TextChoices):
    SELF_EMPLOYED = 'self_employed', 'Self owned business / employment / freelance'
    FARMER = 'farmer', 'Farmers only'
    LABOURER = 'labourer', 'Labourers and private workers (non-salaried)'
    EMPLOYED = 'employed', 'Employed or pensioner persons'


# Which Form 2 template a person signs, based on their professional status
PROFESSION_TEMPLATE = {
    Profession.EMPLOYED: DeclarationTemplate.EMPLOYED,
    Profession.RETIRED: DeclarationTemplate.EMPLOYED,
    Profession.BUSINESS: DeclarationTemplate.SELF_EMPLOYED,
    Profession.FARMER: DeclarationTemplate.FARMER,
    Profession.LABOURER: DeclarationTemplate.LABOURER,
}


class AccommodationType(models.TextChoices):
    BUNGALOW = 'bungalow', 'Bungalow'
    APARTMENT = 'apartment', 'Apartment / Flat'
    TOWN_HOUSE = 'town_house', 'Town House'
    VILLAGE_HOUSE = 'village_house', 'Village House'


class AccommodationStatus(models.TextChoices):
    RENTED = 'rented', 'Rented'
    OWNED = 'owned', 'Self or Family-owned'
    EMPLOYER = 'employer', 'Employer / Government Owned'


class RentPaidBy(models.TextChoices):
    SELF = 'self', 'Self'
    EMPLOYER = 'employer', 'Employer / Govt'
    OTHERS = 'others', 'Others'


class RoomRange(models.TextChoices):
    """Ranges as printed on the form (they overlap at 2 and 4); NONE added for air conditioners."""
    NONE = 'none', 'None'
    R1_2 = '1-2', '1-2'
    R2_4 = '2-4', '2-4'
    R4_6 = '4-6', '4-6'
    ABOVE_6 = 'above_6', 'Above 6'


class AssetIncomeSource(models.TextChoices):
    PROPERTY_RENT = 'property_rent', 'Property Rent'
    LAND_LEASE = 'land_lease', 'Land Lease'
    BANK_DEPOSITS = 'bank_deposits', 'Bank Deposits'
    SHARES = 'shares', 'Shares / Securities'
    OTHER = 'other', 'Other (Specify)'


class AssetTitle(models.TextChoices):
    HOUSE = 'house', 'House'
    BUSINESS = 'business', 'Business'
    LAND_BUILDING = 'land_building', 'Land & Building'
    BANK_BALANCE = 'bank_balance', 'Bank Balance'
    STOCKS = 'stocks', 'Stocks / Prize bond'
    OTHERS = 'others', 'Others / Cattle(s)'


class LandCategory(models.TextChoices):
    RESIDENTIAL = 'residential', 'Residential'
    COMMERCIAL = 'commercial', 'Commercial'
    AGRICULTURAL = 'agricultural', 'Agricultural'
    GOVT_SCHEME = 'govt_scheme', 'Employer / Govt Scheme'


class TransportType(models.TextChoices):
    CAR = 'car', 'Car'
    MOTORCYCLE = 'motorcycle', 'Motorcycle'
    OTHER = 'other', 'Other'


class EducationLevel(models.TextChoices):
    BACHELORS = 'bachelors', 'Bachelors'
    INTERMEDIATE = 'intermediate', 'Intermediate'
    SECONDARY = 'secondary', 'Secondary'


class Division(models.TextChoices):
    FIRST = '1st', '1st'
    SECOND = '2nd', '2nd'
    THIRD = '3rd', '3rd'


class DocumentSlot(models.TextChoices):
    """Page 7 checklist. Item 5 (income declaration) is handled by the Declaration model (Form 2)."""
    CNIC_COPIES = 'cnic_copies', '1. Copies of CNIC/NIC of Student, Father, Mother and/or Guardian'
    DOMICILE = 'domicile', '2. Domicile of Student'
    SALARY_CERTIFICATE = 'salary_certificate', '3. Salary Certificate / Employment Certificate of Father, Mother and/or Guardian'
    SALARY_SLIP = 'salary_slip', '4. Latest Salary Slip / Pension Slip of Father, Mother and/or Guardian'
    BANK_STATEMENTS = 'bank_statements', '6. Bank Statement(s) - Last Six Months of Father, Mother and/or Guardian'
    OTHER_INCOME = 'other_income', '7. Documentary evidence of any other source(s) of income'
    SIBLING_INCOME = 'sibling_income', '8. Salary Slip / Income Certificate of Sibling(s), if employed'
    FEE_RECEIPTS = 'fee_receipts', '9. Latest and previous fee receipts / study vouchers of Student and Sibling(s)'
    PREVIOUS_SCHOLARSHIPS = 'previous_scholarships', '10. Previous Scholarship / Financial Aid awards'
    MEDICAL_BILLS = 'medical_bills', '11. Medical Bills / Medical Expenditure documents'
    UTILITY_BILLS = 'utility_bills', '12. Latest Electricity, Gas, Water and Telephone/Internet Utility Bills'
    RENT_AGREEMENT = 'rent_agreement', '13. Attested Copy of House Rent Agreement'
    HOSTEL_PROOF = 'hostel_proof', '14. Hostel Fee Slip / Hostel Accommodation Proof'
    TRANSPORT_FEE = 'transport_fee', '15. Transport / Bus Fee Slip'
    DEATH_CERTIFICATE = 'death_certificate', '16. Death Certificate of Father/Mother'
    DIVORCE_CERTIFICATE = 'divorce_certificate', '17. Divorce / Separation Certificate or relevant legal document'
    RESULT_CARDS = 'result_cards', '18. Matriculation and Intermediate Result Card / Certificate Copies'
