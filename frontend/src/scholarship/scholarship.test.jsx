import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import ApplicationReview from './ApplicationReview.jsx'
import ApplicationWizard from './ApplicationWizard.jsx'
import ScholarshipHome from './ScholarshipHome.jsx'

const SUMMARY = {
  total_family_earning_gross: 0, total_studying_fees: 0, asset_income: { rows: {}, columns: {}, total: 0 },
  monthly_net_pay: 0, monthly_asset_income: 0, total_monthly_income: 0, total_annual_income: 0,
  accommodation_monthly_rent: 0, accommodation_annual_rent: 0, utilities_monthly_average: 0,
  expenditure: { education: 0, accommodation: 0, utilities: 0, medical: 0, misc: 0 },
  total_monthly_expenditure: 0, total_annual_expenditure: 0, net_monthly_disposable: 0, net_annual_disposable: 0,
  asset_worth: { rows: {}, columns: {}, total: 0 },
}

function makeApp(overrides = {}) {
  return {
    id: 7, cycle: { id: 1, name: 'Fall-26', opens_on: '2026-10-01', closes_on: '2026-11-30' },
    status: 'draft', is_editable: true, submitted_at: null, updated_at: '2026-10-22T10:00:00Z',
    department: 'Computer Science', email: 'ali@gmail.com', age: null,
    registration_id: '233585', program: '', applicant_name: 'Ali Khan', gender: '', marital_status: '', cnic: '',
    date_of_birth: null, domicile: '', present_address: '', permanent_address: '', tel_residence: '', mobile: '',
    total_family_members: null, applicant_gross_income: null, applicant_net_income: null,
    asset_income_other_specify: '', accommodation_type: '', accommodation_status: '', rent_paid_by: '',
    plot_size_sqft: null, covered_area_sqft: null, accommodation_address: '', bedrooms: '', air_conditioners: '',
    monthly_rent: null, other_house_owned: null, other_house_details: '', medical_monthly: null, misc_monthly: null,
    negative_income_explanation: '', owns_transport: null, cattle_count: null, cattle_kind: '', education_loan: null,
    education_loan_details: '', other_financing: '', admission_fee_paid_how: '', last_institution_monthly_fee: null,
    other_scholarships: null, statement_of_purpose: '', undertaking_accepted: false, undertaking_name: '',
    undertaking_date: null, review_remarks: '',
    household_members: [], studying_members: [], parents: [], earning_members: [], asset_income: [],
    utility_months: [], vehicles: [], land_holdings: [], asset_worth: [], education_records: [],
    previous_scholarships: [], status_history: [],
    summary: SUMMARY,
    completion: { form_submitted: false, declarations_required: 0, scans_uploaded: true, physical_copies_received: true, complete: false },
    ...overrides,
  }
}

const NOT_READY = {
  ready: false,
  sections: { personal: { cnic: ['This field is required.'] } },
  missing_documents: ['domicile'],
  problems: [],
}

let calls
/** routes: list of [method, urlPart, handler(body) -> { status, body }] */
function mockApi(routes) {
  calls = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, opts = {}) => {
    const method = opts.method || 'GET'
    const body = opts.body ? JSON.parse(opts.body) : undefined
    calls.push({ method, url, body })
    const route = routes.find(([m, part]) => m === method && url.includes(part))
    if (!route) throw new Error(`Unexpected request ${method} ${url}`)
    const { status = 200, body: data } = route[2](body)
    return { ok: status < 400, status, json: async () => data }
  })
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/scholarships" element={<ScholarshipHome />} />
        <Route path="/scholarships/:id/review" element={<ApplicationReview />} />
        <Route path="/scholarships/:id/:step" element={<ApplicationWizard />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

test('home lists open cycles and starts an application', async () => {
  mockApi([
    ['GET', '/scholarships/cycles/open/', () => ({ body: [{ id: 1, name: 'Fall-26', opens_on: '2026-10-01', closes_on: '2026-11-30' }] })],
    ['GET', '/scholarships/applications/7/readiness/', () => ({ body: NOT_READY })],
    ['GET', '/scholarships/applications/7/', () => ({ body: makeApp() })],
    ['GET', '/scholarships/applications/', () => ({ body: { count: 0, results: [] } })],
    ['POST', '/scholarships/applications/', () => ({ status: 201, body: makeApp() })],
  ])
  renderAt('/scholarships')
  expect(await screen.findByText('Fall-26')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Start application' }))
  expect(await screen.findByRole('heading', { name: 'Step 1: Personal details' })).toBeInTheDocument()
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ cycle: 1 })
  expect(screen.getByLabelText(/Applicant's name/)).toHaveValue('Ali Khan') // prefilled
})

test('a server error is shown beside the field it belongs to', async () => {
  mockApi([
    ['GET', '/readiness/', () => ({ body: NOT_READY })],
    ['GET', '/scholarships/applications/7/', () => ({ body: makeApp() })],
    ['PATCH', '/sections/personal/', () => ({ status: 400, body: { cnic: ['Enter a CNIC as 12345-1234567-1 (13 digits).'] } })],
  ])
  renderAt('/scholarships/7/personal')
  const cnic = await screen.findByLabelText(/CNIC/)
  await userEvent.type(cnic, '123')
  await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Nothing was saved')
  expect(cnic).toHaveAttribute('aria-invalid', 'true')
  expect(cnic).toHaveAccessibleDescription('Enter a CNIC as 12345-1234567-1 (13 digits).')
  expect(calls.find((c) => c.method === 'PATCH').body.cnic).toBe('123')
})

test('saving successfully shows a confirmation and keeps the server values', async () => {
  mockApi([
    ['GET', '/readiness/', () => ({ body: NOT_READY })],
    ['GET', '/scholarships/applications/7/', () => ({ body: makeApp() })],
    ['PATCH', '/sections/personal/', (body) => ({ body: makeApp({ ...body, cnic: '36302-1234567-1', updated_at: '2026-10-22T10:05:00Z' }) })],
  ])
  renderAt('/scholarships/7/personal')
  await userEvent.type(await screen.findByLabelText(/CNIC/), '3630212345671')
  await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Saved as draft.')
  expect(screen.getByLabelText(/CNIC/)).toHaveValue('36302-1234567-1') // normalised by the server
})

test('row errors land on the right row even when empty rows are skipped', async () => {
  mockApi([
    ['GET', '/readiness/', () => ({ body: NOT_READY })],
    ['GET', '/scholarships/applications/7/', () => ({ body: makeApp() })],
    ['PATCH', '/sections/household/', () => ({ status: 400, body: { household_members: { 0: { relationship: ['"x" is not a valid choice.'] } } } })],
  ])
  renderAt('/scholarships/7/household')
  const add = await screen.findByRole('button', { name: 'Add family member' })
  await userEvent.click(add) // row 1 stays empty
  await userEvent.click(add) // row 2 is filled
  await userEvent.type(screen.getByLabelText('Row 2: Name'), 'Aslam')
  await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))

  const sent = calls.find((c) => c.method === 'PATCH').body.household_members
  expect(sent).toEqual([{ name: 'Aslam', relationship: '', marital_status: '', remarks: '' }]) // empty row 1 not sent
  expect(await screen.findByText('"x" is not a valid choice.')).toBeInTheDocument()
  expect(screen.getByLabelText('Row 2: Relationship')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByLabelText('Row 1: Relationship')).not.toHaveAttribute('aria-invalid')
})

test('parents: deceased father asks for a guardian and errors show under the right person', async () => {
  mockApi([
    ['GET', '/readiness/', () => ({ body: NOT_READY })],
    ['GET', '/scholarships/applications/7/', () => ({ body: makeApp() })],
    ['PATCH', '/sections/parents/', () => ({ status: 400, body: { parents: { 1: { cnic: ['Enter a CNIC as 12345-1234567-1 (13 digits).'] } } } })],
  ])
  renderAt('/scholarships/7/parents')
  const father = await screen.findByRole('group', { name: 'Father (Q12-19)' })
  await userEvent.selectOptions(within(father).getByLabelText(/Status/), 'deceased')
  expect(screen.getByText('A guardian is required because your father is deceased.')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
  const mother = screen.getByRole('group', { name: 'Mother (Q20-23)' })
  expect(await within(mother).findByText('Enter a CNIC as 12345-1234567-1 (13 digits).')).toBeInTheDocument()
  expect(within(father).queryByText(/Enter a CNIC/)).not.toBeInTheDocument()
  expect(calls.find((c) => c.method === 'PATCH').body.parents.map((p) => p.role)).toEqual(['father', 'mother'])
})

test('education months are sent as the first day of the month', async () => {
  mockApi([
    ['GET', '/readiness/', () => ({ body: NOT_READY })],
    ['GET', '/scholarships/applications/7/', () => ({ body: makeApp() })],
    ['PATCH', '/sections/education/', (body) => ({ body: makeApp({ updated_at: 'x2', education_records: body.education_records }) })],
  ])
  renderAt('/scholarships/7/education')
  await userEvent.type(await screen.findByLabelText('Intermediate: Name and location of institute'), 'Govt College')
  await userEvent.type(screen.getByLabelText('Intermediate: From'), '2020-09')
  await userEvent.type(screen.getByLabelText('Intermediate: To'), '2022-06')
  await userEvent.type(screen.getByLabelText('Intermediate: %age'), '78')
  await userEvent.click(screen.getByRole('button', { name: 'Save draft' }))
  const records = calls.find((c) => c.method === 'PATCH').body.education_records
  expect(records).toEqual([expect.objectContaining({
    level: 'intermediate', institute: 'Govt College', from_month: '2020-09-01', to_month: '2022-06-01', percentage: '78',
  })])
})

test('a submitted application is read-only', async () => {
  mockApi([
    ['GET', '/scholarships/applications/7/', () => ({ body: makeApp({ status: 'placement_verification', is_editable: false, submitted_at: '2026-10-20T09:00:00Z' }) })],
  ])
  renderAt('/scholarships/7/personal')
  expect(await screen.findByText(/can no longer be changed/)).toBeInTheDocument()
  expect(screen.getByLabelText(/CNIC/)).toBeDisabled()
  expect(screen.queryByRole('button', { name: 'Save draft' })).not.toBeInTheDocument()
})

test('review lists what is missing and keeps submit disabled', async () => {
  mockApi([
    ['GET', '/readiness/', () => ({ body: NOT_READY })],
    ['GET', '/scholarships/applications/7/', () => ({ body: makeApp() })],
  ])
  renderAt('/scholarships/7/review')
  expect(await screen.findByText('Still needed before you can submit')).toBeInTheDocument()
  expect(screen.getByText('Cnic is required.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Fix' })).toHaveAttribute('href', '/scholarships/7/personal?check=1')
  expect(screen.getByText('2. Domicile of Student')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Submit application' })).toBeDisabled()
})

test('review submits after confirmation when ready', async () => {
  mockApi([
    ['GET', '/readiness/', () => ({ body: { ready: true, sections: {}, missing_documents: [], problems: [] } })],
    ['GET', '/scholarships/applications/7/', () => ({ body: makeApp({ summary: { ...SUMMARY, total_monthly_income: 72000, net_monthly_disposable: 30000 } }) })],
    ['POST', '/submit/', () => ({ body: makeApp({ status: 'placement_verification', is_editable: false, submitted_at: '2026-10-22T11:00:00Z' }) })],
  ])
  renderAt('/scholarships/7/review')
  expect(await screen.findByText('Rs. 72,000')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Submit application' }))
  await userEvent.click(screen.getByRole('button', { name: 'Yes, submit' }))
  expect(await screen.findByRole('status')).toHaveTextContent('has been submitted')
  expect(screen.getByText(/can no longer be changed/)).toBeInTheDocument()
  expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1)
})
