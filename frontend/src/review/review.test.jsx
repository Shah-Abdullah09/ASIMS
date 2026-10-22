import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App.jsx'
import { AuthProvider } from '../AuthContext.jsx'
import ReviewDetail from './ReviewDetail.jsx'
import ReviewList from './ReviewList.jsx'

const ROW = (over = {}) => ({
  id: 7, applicant_name: 'Ali Khan', registration_id: '233585', cnic: '36302-1234567-1', email: 'ali@gmail.com',
  department: 'Computer Science', cycle: 1, cycle_name: 'Fall-26', status: 'pending', submitted_at: '2026-10-20T09:00:00Z',
  reviewed_at: null,
  completion: { form_submitted: true, declarations_required: 1, scans_uploaded: false, physical_copies_received: false, complete: false },
  ...over,
})

const SUMMARY = {
  total_family_earning_gross: 80000, total_studying_fees: 5000, monthly_net_pay: 72000, monthly_asset_income: 0,
  total_monthly_income: 72000, total_annual_income: 864000, accommodation_monthly_rent: 0, accommodation_annual_rent: 0,
  utilities_monthly_average: 7000, expenditure: { education: 5000, accommodation: 0, utilities: 7000, medical: 0, misc: 5000 },
  total_monthly_expenditure: 17000, total_annual_expenditure: 204000, net_monthly_disposable: 55000,
  net_annual_disposable: 660000, asset_worth: { rows: {}, columns: {}, total: 0 },
}

const DECL = {
  id: 3, person: 'Father', person_name: 'Muhammad Aslam', template: 'employed', is_complete: false, can_upload_scan: true,
  scan: { original_name: 'stamp.jpg', content_type: 'image/jpeg', size: 300000, uploaded_at: '2026-10-21T10:00:00Z',
    download_url: '/api/v1/scholarships/declarations/3/scan/' },
  physical_received_on: null, physical_received_by: null, printable: { title: 'Employed or pensioner persons' },
}

const DETAIL = (over = {}) => ({
  ...ROW(), id: 7, cycle: { id: 1, name: 'Fall-26' }, age: 22, date_of_birth: '2004-05-01', program: 'BS Software Engineering',
  gender: 'male', marital_status: 'single', domicile: 'Multan', mobile: '03001234567', tel_residence: '',
  present_address: 'House 1, Multan', permanent_address: 'House 1, Multan', total_family_members: 4,
  student: { id: 2, full_name: 'Ali Khan', email: 'ali@gmail.com', registration_id: '233585', department: 'Computer Science' },
  reviewed_by: null, review_remarks: '', applicant_gross_income: 0, applicant_net_income: 0, asset_income_other_specify: '',
  accommodation_type: 'town_house', accommodation_status: 'owned', rent_paid_by: '', monthly_rent: null, plot_size_sqft: 1125,
  covered_area_sqft: 900, bedrooms: '1-2', air_conditioners: 'none', accommodation_address: 'House 1', other_house_owned: false,
  other_house_details: '', negative_income_explanation: '', owns_transport: false, cattle_count: 0, cattle_kind: '',
  education_loan: false, education_loan_details: '', other_financing: '', admission_fee_paid_how: 'Savings',
  last_institution_monthly_fee: 3000, other_scholarships: false, statement_of_purpose: 'My father is the only earner.',
  undertaking_accepted: true, undertaking_name: 'Ali Khan', undertaking_date: '2026-10-20',
  household_members: [{ name: 'Muhammad Aslam', relationship: 'father', marital_status: 'married', remarks: '' }],
  studying_members: [], earning_members: [{ name: 'Muhammad Aslam', relationship: 'father', occupation: 'Govt', organization: 'WAPDA',
    designation: 'Assistant', gross_pay: 80000, net_pay: 72000, remarks: '' }],
  parents: [{ role: 'father', name: 'Muhammad Aslam', cnic: '36302-1111111-1', status: 'alive', profession: 'employed',
    employer: 'WAPDA Multan', gross_monthly_income: 80000, net_monthly_income: 72000 }],
  asset_income: [], utility_months: [], vehicles: [], land_holdings: [], asset_worth: [], education_records: [],
  previous_scholarships: [],
  documents: [
    { slot: 'domicile', label: '2. Domicile of Student', kind: 'always', required: true, missing: false, max_files: 5, reason: '',
      files: [{ id: 11, original_name: 'domicile.pdf', size: 204800, uploaded_at: '2026-10-20T09:00:00Z',
        download_url: '/api/v1/scholarships/documents/11/download/' }] },
    { slot: 'result_cards', label: '18. Matriculation and Intermediate Result Cards', kind: 'always', required: true,
      missing: true, max_files: 5, reason: '', files: [] },
    { slot: 'hostel_proof', label: '14. Hostel Fee Slip', kind: 'optional', required: false, missing: false, max_files: 5, reason: '', files: [] },
  ],
  declarations: [DECL],
  status_history: [{ from_status: 'draft', to_status: 'pending', remarks: 'Submitted by the student.', changed_by: 'Ali Khan',
    changed_by_role: 'Student', changed_at: '2026-10-20T09:00:00Z' }],
  summary: SUMMARY,
  ...over,
})

let calls
function mockApi(routes) {
  calls = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, opts = {}) => {
    const method = opts.method || 'GET'
    const body = opts.body ? JSON.parse(opts.body) : undefined
    calls.push({ method, url, body })
    const route = routes.find(([m, part]) => m === method && (typeof part === 'string' ? url.includes(part) : part.test(url)))
    if (!route) throw new Error(`Unexpected request ${method} ${url}`)
    const { status = 200, body: data, blob } = route[2](body, url)
    return { ok: status < 400, status, json: async () => data, blob: async () => blob }
  })
}

const LISTS = [
  ['GET', '/scholarships/cycles/', () => ({ body: [{ id: 1, name: 'Fall-26' }, { id: 2, name: 'Spring-26' }] })],
  ['GET', '/departments/', () => ({ body: [{ id: 5, name: 'Computer Science', code: 'CS' }] })],
]

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/review" element={<ReviewList />} />
        <Route path="/review/:id" element={<ReviewDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

const listCalls = () => calls.filter((c) => c.url.includes('/review/applications/')).map((c) => c.url.split('?')[1] || '')

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

// ---------- list ----------

test('list shows submitted applications with completeness', async () => {
  mockApi([...LISTS, ['GET', '/review/applications/', () => ({ body: { count: 2, next: null, previous: null, results: [
    ROW(), ROW({ id: 8, applicant_name: 'Sara Ahmed', status: 'approved',
      completion: { form_submitted: true, declarations_required: 1, scans_uploaded: true, physical_copies_received: true, complete: true } }),
  ] } })]])
  renderAt('/review')
  expect(await screen.findByText('2 applications.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Ali Khan' })).toHaveAttribute('href', '/review/7')
  expect(screen.getByText('Missing: Form 2 scan, original')).toBeInTheDocument()
  expect(screen.getByText('Complete')).toBeInTheDocument()
})

test('filters, search and sorting go into the request and the address', async () => {
  mockApi([...LISTS, ['GET', '/review/applications/', () => ({ body: { count: 0, next: null, previous: null, results: [] } })]])
  renderAt('/review')
  await screen.findByText('0 applications.')
  await userEvent.selectOptions(await screen.findByLabelText('Cycle'), '1')
  await userEvent.selectOptions(screen.getByLabelText('Status'), 'under_review')
  await userEvent.selectOptions(screen.getByLabelText('Completeness'), 'false')
  await userEvent.type(screen.getByLabelText('Search'), '233585')
  await userEvent.click(screen.getByRole('button', { name: 'Search' }))

  const last = new URLSearchParams(listCalls().at(-1))
  expect(Object.fromEntries(last)).toEqual({ cycle: '1', status: 'under_review', complete: 'false', search: '233585' })
  expect(await screen.findByText('0 applications match the filters.')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  expect(listCalls().at(-1)).toBe('')
})

test('pagination asks for the next page', async () => {
  mockApi([...LISTS, ['GET', '/review/applications/', (_, url) => ({ body: {
    count: 25, next: url.includes('page=2') ? null : 'x', previous: url.includes('page=2') ? 'y' : null,
    results: [ROW()],
  } })]])
  renderAt('/review')
  await userEvent.click(await screen.findByRole('button', { name: 'Next' }))
  expect(await screen.findByText('Page 2')).toBeInTheDocument()
  expect(listCalls().at(-1)).toBe('page=2')
})

// ---------- detail ----------

const detailApi = (extra = [], detail = DETAIL) => mockApi([
  ...extra,
  ['GET', '/review/applications/7/', () => ({ body: detail() })],
])

test('detail shows the answers, totals, documents and Form 2', async () => {
  detailApi()
  renderAt('/review/7')
  expect(await screen.findByRole('heading', { name: 'Ali Khan', level: 1 })).toBeInTheDocument()
  expect(screen.getByText('36302-1234567-1')).toBeInTheDocument()
  expect(screen.getByText('BS Software Engineering')).toBeInTheDocument()
  expect(screen.getByText('1 May 2004 (age 22)')).toBeInTheDocument()
  expect(screen.getAllByText('WAPDA Multan').length).toBeGreaterThan(0)
  expect(screen.getByText('Rs. 55,000')).toBeInTheDocument() // monthly disposable
  expect(screen.getByText('1 required document(s) missing.')).toBeInTheDocument()
  expect(screen.queryByRole('listitem', { name: '14. Hostel Fee Slip' })).not.toBeInTheDocument() // empty optional slot hidden
  const form2 = screen.getByRole('listitem', { name: 'Form 2: Father' })
  expect(within(form2).getByText(/Scan: stamp.jpg/)).toBeInTheDocument()
  expect(within(form2).getByText('Original not received')).toBeInTheDocument()
})

test('a document opens through the protected link', async () => {
  URL.createObjectURL = vi.fn(() => 'blob:doc')
  URL.revokeObjectURL = vi.fn()
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  detailApi([['GET', '/documents/11/download/', () => ({ blob: new Blob(['%PDF']) })]])
  renderAt('/review/7')
  const domicile = await screen.findByRole('listitem', { name: '2. Domicile of Student' })
  await userEvent.click(within(domicile).getByRole('button', { name: 'View' }))
  expect(calls.some((c) => c.url === '/api/v1/scholarships/documents/11/download/')).toBe(true)
  expect(click).toHaveBeenCalled()
})

test('rejecting without remarks shows the server message beside remarks', async () => {
  detailApi([['POST', '/status/', () => ({ status: 400, body: { remarks: ['Give the reason for rejecting, so the student knows why.'] } })]])
  renderAt('/review/7')
  await userEvent.selectOptions(await screen.findByLabelText('New status'), 'rejected')
  expect(screen.getByText('* required to reject')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Save decision' }))
  const remarks = screen.getByLabelText(/Remarks/)
  expect(await screen.findByText('Give the reason for rejecting, so the student knows why.')).toBeInTheDocument()
  expect(remarks).toHaveAttribute('aria-invalid', 'true')
})

test('approving an incomplete application is explained before and after saving', async () => {
  detailApi([['POST', '/status/', () => ({ status: 400, body: { status: ['The application is not complete yet. Missing: original stamp paper(s).'] } })]])
  renderAt('/review/7')
  await userEvent.selectOptions(await screen.findByLabelText('New status'), 'approved')
  expect(screen.getByText(/Approval needs a complete application/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Save decision' }))
  expect(await screen.findByText(/not complete yet/)).toBeInTheDocument()
})

test('a decision is saved with remarks and added to the history', async () => {
  detailApi([['POST', '/status/', (body) => ({ body: DETAIL({
    status: body.status, review_remarks: body.remarks, reviewed_by: 'Sana Placement', reviewed_at: '2026-10-23T09:00:00Z',
    status_history: [...DETAIL().status_history, { from_status: 'pending', to_status: body.status, remarks: body.remarks,
      changed_by: 'Sana Placement', changed_by_role: 'Placement Officer', changed_at: '2026-10-23T09:00:00Z' }],
  }) })]])
  renderAt('/review/7')
  await userEvent.selectOptions(await screen.findByLabelText('New status'), 'under_review')
  await userEvent.type(screen.getByLabelText(/Remarks/), 'Checking the salary slip.')
  await userEvent.click(screen.getByRole('button', { name: 'Save decision' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Saved: Under review.')
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ status: 'under_review', remarks: 'Checking the salary slip.' })
  const history = screen.getByRole('heading', { name: 'History' }).nextElementSibling
  expect(within(history).getByText('Checking the salary slip.')).toBeInTheDocument()
  expect(within(history).getByText(/Sana Placement \(Placement Officer\)/)).toBeInTheDocument()
})

test('the office marks the original received with a date, and can undo it', async () => {
  let received = false
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  detailApi([
    ['POST', '/declarations/3/receive/', () => { received = true; return { body: {} } }],
    ['DELETE', '/declarations/3/receive/', () => { received = false; return { body: {} } }],
  ], () => DETAIL({ declarations: [received
    ? { ...DECL, physical_received_on: '2026-10-22', physical_received_by: 'Sana Placement', is_complete: true }
    : DECL] }))
  renderAt('/review/7')
  const date = await screen.findByLabelText('Received on')
  await userEvent.clear(date)
  await userEvent.type(date, '2026-10-22')
  await userEvent.click(screen.getByRole('button', { name: 'Mark original received' }))
  expect(await screen.findByText('Original received on 22 Oct 2026 by Sana Placement')).toBeInTheDocument()
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ received_on: '2026-10-22' })

  await userEvent.click(screen.getByRole('button', { name: 'Undo received' }))
  expect(await screen.findByText('Original not received')).toBeInTheDocument()
})

// ---------- who can open the staff pages ----------

function renderApp(path, role) {
  localStorage.setItem('asims_tokens', JSON.stringify({ access: 'a', refresh: 'r' }))
  mockApi([
    ['GET', '/auth/me/', () => ({ body: { id: 1, full_name: 'Test User', role, email: 'u@x.com' } })],
    ...LISTS,
    ['GET', '/review/applications/', () => ({ body: { count: 0, next: null, previous: null, results: [] } })],
  ])
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>)
}

test('students are sent back to the dashboard from the staff pages', async () => {
  renderApp('/review', 'student')
  expect(await screen.findByText('Welcome, Test User')).toBeInTheDocument()
  expect(calls.some((c) => c.url.includes('/review/applications/'))).toBe(false)
})

test.each(['placement_officer', 'administrator'])('%s can open the staff list from the dashboard link', async (role) => {
  renderApp('/dashboard', role)
  await userEvent.click(await screen.findByRole('link', { name: 'Review scholarship applications' }))
  expect(await screen.findByRole('heading', { name: 'Scholarship applications' })).toBeInTheDocument()
})
