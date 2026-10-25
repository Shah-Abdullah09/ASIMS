// Option lists for the AU Need Based Financial Grant form. Values must match the backend choices.
const opts = (pairs) => pairs.map(([value, label]) => ({ value, label }))

export const GENDER = opts([['male', 'Male'], ['female', 'Female']])
export const MARITAL = opts([['single', 'Single'], ['married', 'Married'], ['widowed', 'Widowed'], ['divorced', 'Divorced']])
export const RELATIONSHIP = opts([
  ['father', 'Father'], ['mother', 'Mother'], ['brother', 'Brother'], ['sister', 'Sister'], ['spouse', 'Spouse'],
  ['son', 'Son'], ['daughter', 'Daughter'], ['grandparent', 'Grandparent'], ['guardian', 'Guardian'], ['other', 'Other'],
])
export const LIFE_STATUS = opts([['alive', 'Alive'], ['deceased', 'Deceased']])
export const PROFESSION = opts([
  ['employed', 'Employed'], ['retired', 'Retired / Pensioner'], ['business', 'Business / Self-employed / Freelance'],
  ['farmer', 'Farmer'], ['labourer', 'Labourer / Private worker'], ['not_earning', 'Not earning'],
])
export const ACCOMMODATION_TYPE = opts([
  ['bungalow', 'Bungalow'], ['apartment', 'Apartment / Flat'], ['town_house', 'Town House'], ['village_house', 'Village House'],
])
export const ACCOMMODATION_STATUS = opts([
  ['rented', 'Rented'], ['owned', 'Self or Family-owned'], ['employer', 'Employer / Government Owned'],
])
export const RENT_PAID_BY = opts([['self', 'Self'], ['employer', 'Employer / Govt'], ['others', 'Others']])
export const BEDROOMS = opts([['1-2', '1-2'], ['2-4', '2-4'], ['4-6', '4-6'], ['above_6', 'Above 6']])
export const AIR_CONDITIONERS = opts([['none', 'None'], ['1-2', '1-2'], ['2-4', '2-4'], ['4-6', '4-6'], ['above_6', 'Above 6']])
export const TRANSPORT = opts([['car', 'Car'], ['motorcycle', 'Motorcycle'], ['other', 'Other']])
export const DIVISION = opts([['1st', '1st'], ['2nd', '2nd'], ['3rd', '3rd']])

export const ASSET_INCOME_SOURCES = opts([
  ['property_rent', 'Property Rent'], ['land_lease', 'Land Lease'], ['bank_deposits', 'Bank Deposits'],
  ['shares', 'Shares / Securities'], ['other', 'Other (Specify)'],
])
export const ASSET_TITLES = opts([
  ['house', 'House'], ['business', 'Business'], ['land_building', 'Land & Building'], ['bank_balance', 'Bank Balance'],
  ['stocks', 'Stocks / Prize bond'], ['others', 'Others / Cattle(s)'],
])
export const LAND_CATEGORIES = opts([
  ['residential', 'Residential'], ['commercial', 'Commercial'], ['agricultural', 'Agricultural'],
  ['govt_scheme', 'Employer / Govt Scheme'],
])
export const EDUCATION_LEVELS = opts([['bachelors', 'Bachelors'], ['intermediate', 'Intermediate'], ['secondary', 'Secondary']])

export const DOCUMENT_LABELS = {
  cnic_copies: '1. Copies of CNIC/NIC of Student, Father, Mother and/or Guardian',
  domicile: '2. Domicile of Student',
  salary_certificate: '3. Salary Certificate / Employment Certificate',
  salary_slip: '4. Latest Salary Slip / Pension Slip',
  bank_statements: '6. Bank Statement(s) - Last Six Months',
  other_income: '7. Evidence of any other source(s) of income',
  sibling_income: '8. Salary Slip / Income Certificate of Sibling(s)',
  fee_receipts: '9. Latest and previous fee receipts / study vouchers',
  previous_scholarships: '10. Previous Scholarship / Financial Aid awards',
  medical_bills: '11. Medical Bills / Medical Expenditure documents',
  utility_bills: '12. Latest Utility Bills',
  rent_agreement: '13. Attested Copy of House Rent Agreement',
  hostel_proof: '14. Hostel Fee Slip / Hostel Accommodation Proof',
  transport_fee: '15. Transport / Bus Fee Slip',
  death_certificate: '16. Death Certificate of Father/Mother',
  divorce_certificate: '17. Divorce / Separation Certificate',
  result_cards: '18. Matriculation and Intermediate Result Cards',
}

/** Stages of the approval chain, in order. */
export const STATUS_LABELS = {
  draft: 'Draft',
  placement_verification: 'Placement verification',
  returned: 'Returned to student',
  dac_review: 'DAC review',
  awaiting_forwarding: 'Awaiting forwarding',
  director_review: 'Director review',
  registrar_review: 'Registrar review',
  vc_review: 'VC review',
  awaiting_fee_adjustment: 'Awaiting fee adjustment',
  rejected: 'Rejected',
}
