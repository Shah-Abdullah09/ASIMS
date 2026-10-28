import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App.jsx'
import { AuthProvider } from '../AuthContext.jsx'

const ROW = (over = {}) => ({
  id: 7, applicant_name: 'Ali Khan', registration_id: '233585', cnic: '36302-1234567-1', email: 'ali@gmail.com',
  department: 'Computer Science', cycle: 1, cycle_name: 'Fall-26', status: 'placement_verification', submitted_at: '2026-10-20T09:00:00Z',
  reviewed_at: null, scholarship_percentage: null,
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
  status_history: [{ from_status: 'draft', to_status: 'placement_verification', action: 'submit', percentage: null,
    remarks: 'Submitted by the student.', changed_by: 'Ali Khan', changed_by_role: 'Student', changed_at: '2026-10-20T09:00:00Z' }],
  available_actions: [
    { action: 'verify', label: 'Verify and send to DAC', to_status: 'dac_review', remarks_required: false, percentage: null },
    { action: 'return', label: 'Return to student', to_status: 'returned', remarks_required: true, percentage: null },
    { action: 'reject', label: 'Reject', to_status: 'rejected', remarks_required: true, percentage: null },
  ],
  summary: SUMMARY,
  ...over,
})

let calls
let signedInRole = 'placement_officer'
function mockApi(routes) {
  calls = []
  const me = ['GET', '/auth/me/', () => ({ body: { id: 1, full_name: 'Test User', role: signedInRole, email: 'u@x.com' } })]
  routes = [me, ...routes]
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

/** The real app at `path`, signed in with `role` (the fake API answers /auth/me/ with it). */
function renderAt(path, role = 'placement_officer') {
  signedInRole = role
  localStorage.setItem('asims_tokens', JSON.stringify({ access: 'a', refresh: 'r' }))
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>)
}

const listCalls = () => calls.filter((c) => c.url.includes('/review/applications/')).map((c) => c.url.split('?')[1] || '')

beforeEach(() => { localStorage.clear(); signedInRole = 'placement_officer' })
afterEach(() => vi.restoreAllMocks())

// ---------- list ----------

test('list shows submitted applications with completeness', async () => {
  mockApi([...LISTS, ['GET', '/review/applications/', () => ({ body: { count: 2, next: null, previous: null, results: [
    ROW(), ROW({ id: 8, applicant_name: 'Sara Ahmed', status: 'dac_review',
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
  await userEvent.selectOptions(screen.getByLabelText('Status'), 'dac_review')
  await userEvent.selectOptions(screen.getByLabelText('Completeness'), 'false')
  await userEvent.type(screen.getByLabelText('Search'), '233585')
  await userEvent.click(screen.getByRole('button', { name: 'Search' }))

  const last = new URLSearchParams(listCalls().at(-1))
  expect(Object.fromEntries(last)).toEqual({ cycle: '1', status: 'dac_review', complete: 'false', search: '233585' })
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
  detailApi([['POST', '/actions/', () => ({ status: 400, body: { remarks: ['Remarks are required for this action, so the reason is on record.'] } })]])
  renderAt('/review/7')
  await userEvent.selectOptions(await screen.findByLabelText('Action'), 'reject')
  expect(screen.getByText('* required')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Reject' }))
  const remarks = screen.getByLabelText(/Remarks/)
  expect(await screen.findByText('Remarks are required for this action, so the reason is on record.')).toBeInTheDocument()
  expect(remarks).toHaveAttribute('aria-invalid', 'true')
})

test('verifying an incomplete application is explained before and after saving', async () => {
  detailApi([['POST', '/actions/', () => ({ status: 400, body: { action: ['The application is not complete yet. Missing: original stamp paper(s).'] } })]])
  renderAt('/review/7')
  expect(await screen.findByText(/Verifying needs a complete application/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Verify and send to DAC' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('not complete yet')
})

test('a percentage field appears only for actions that take one', async () => {
  detailApi([])
  renderAt('/review/7')
  await screen.findByLabelText('Action')
  expect(screen.queryByLabelText(/Scholarship percentage/)).not.toBeInTheDocument()
})

test('with no action at this stage the panel says so', async () => {
  detailApi([], () => DETAIL({ available_actions: [], status: 'director_review' }))
  renderAt('/review/7')
  expect(await screen.findByText('You have no action at this stage.')).toBeInTheDocument()
  expect(screen.queryByLabelText('Action')).not.toBeInTheDocument()
})

test('an action is saved with remarks and added to the history', async () => {
  detailApi([['POST', '/actions/', (body) => ({ body: DETAIL({
    status: 'returned', review_remarks: body.remarks, reviewed_by: 'Sana Placement', reviewed_at: '2026-10-23T09:00:00Z',
    available_actions: [],
    status_history: [...DETAIL().status_history, { from_status: 'placement_verification', to_status: 'returned', action: 'return',
      percentage: null, remarks: body.remarks, changed_by: 'Sana Placement', changed_by_role: 'Placement Officer', changed_at: '2026-10-23T09:00:00Z' }],
  }) })]])
  renderAt('/review/7')
  await userEvent.selectOptions(await screen.findByLabelText('Action'), 'return')
  await userEvent.type(screen.getByLabelText(/Remarks/), 'Bank statement is unreadable.')
  await userEvent.click(screen.getByRole('button', { name: 'Return to student' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Done: the case is now at "Returned to student".')
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ action: 'return', remarks: 'Bank statement is unreadable.' })
  const history = screen.getByRole('heading', { name: 'History' }).nextElementSibling
  expect(within(history).getByText('Bank statement is unreadable.')).toBeInTheDocument()
  expect(within(history).getByText('Returned for corrections by Placement Officer')).toBeInTheDocument()
  expect(within(history).getByText(/Sana Placement, .* · now Returned to student/)).toBeInTheDocument()
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
  mockApi([
    ...LISTS,
    ['GET', '/review/applications/', () => ({ body: { count: 0, next: null, previous: null, results: [] } })],
  ])
  return renderAt(path, role)
}

test('students are sent back to the dashboard from the staff pages', async () => {
  renderApp('/review', 'student')
  expect(await screen.findByText('Welcome, Test User')).toBeInTheDocument()
  expect(calls.some((c) => c.url.includes('/review/applications/'))).toBe(false)
})

test.each(['placement_officer', 'administrator'])('%s can open the staff list from the dashboard link', async (role) => {
  renderApp('/dashboard', role)
  await userEvent.click(await screen.findByRole('link', { name: 'My work: Scholarship applications' }))
  expect(await screen.findByRole('heading', { name: 'Scholarship applications' })).toBeInTheDocument()
})

// ---------- Phase 3: staff tools per role ----------

const OPEN_FLAG = { id: 4, section: 'income', section_label: 'Income', note: 'Net pay missing.', flagged_by: 'Sana Placement',
  flagged_at: '2026-10-24T09:00:00Z', is_open: true, resolved_at: null, resolved_by: null, resolution: '' }

test('Placement marks a file verified or asks for clarification with a note', async () => {
  detailApi([['POST', '/documents/11/review/', () => ({ body: {} })]])
  renderAt('/review/7')
  const domicile = await screen.findByRole('listitem', { name: '2. Domicile of Student' })
  expect(within(domicile).getByText('Not reviewed')).toBeInTheDocument()
  await userEvent.click(within(domicile).getByRole('button', { name: 'Verified' }))
  await userEvent.click(within(domicile).getByRole('button', { name: 'Needs clarification' }))
  await userEvent.type(within(domicile).getByLabelText(/What is unclear/), 'Stamp is not readable.')
  await userEvent.click(within(domicile).getByRole('button', { name: 'Save' }))
  const posts = calls.filter((c) => c.method === 'POST').map((c) => c.body)
  expect(posts).toEqual([{ review_status: 'verified', note: '' },
    { review_status: 'needs_clarification', note: 'Stamp is not readable.' }])
})

test('Placement flags a section and clears an open flag', async () => {
  detailApi([
    ['POST', '/flags/', () => ({ status: 201, body: {} })],
    ['DELETE', '/flags/4/', () => ({ body: {} })],
  ], () => DETAIL({ flags: [OPEN_FLAG] }))
  renderAt('/review/7')
  const panel = await screen.findByRole('form', { name: 'Request a correction' })
  expect(screen.getByText(/Net pay missing\./)).toBeInTheDocument()
  await userEvent.selectOptions(within(panel).getByLabelText('Section'), 'parents')
  await userEvent.type(within(panel).getByLabelText(/What should the student correct/), "Mother's CNIC is wrong.")
  await userEvent.click(within(panel).getByRole('button', { name: 'Flag section' }))
  await userEvent.click(screen.getByRole('button', { name: 'Clear' }))
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ section: 'parents', note: "Mother's CNIC is wrong." })
  expect(calls.some((c) => c.method === 'DELETE' && c.url.endsWith('/flags/4/'))).toBe(true)
})

test('an approver sees the DAC interview and decides, without Placement tools', async () => {
  detailApi([], () => DETAIL({
    status: 'director_review', interview_date: '2026-10-25', interview_remarks: 'Genuine need.',
    interview_recorded_by: 'Dr Cs', scholarship_percentage: 60, flags: [],
    available_actions: [
      { action: 'approve', label: 'Approve', to_status: 'registrar_review', remarks_required: false, percentage: 'optional' },
      { action: 'reject', label: 'Reject', to_status: 'rejected', remarks_required: true, percentage: null },
    ],
  }))
  renderAt('/review/7', 'director')
  const interview = await screen.findByRole('region', { name: 'DAC interview' })
  expect(within(interview).getByText('Genuine need.')).toBeInTheDocument()
  expect(within(interview).getByText('60% of the semester tuition fee')).toBeInTheDocument()
  expect(screen.getByLabelText(/Scholarship percentage/)).toHaveValue(60)
  expect(screen.queryByRole('button', { name: 'Verified' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Mark original received' })).not.toBeInTheDocument()
  expect(screen.queryByRole('form', { name: 'Request a correction' })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Director review queue' })).toBeInTheDocument()
})

test('the DAC records the interview, shortlists, and the case leaves the queue', async () => {
  const atDac = { status: 'dac_review', flags: [], available_actions: [
    { action: 'shortlist', label: 'Shortlist', to_status: 'awaiting_forwarding', remarks_required: false, percentage: 'required' },
    { action: 'not_shortlisted', label: 'Not shortlisted', to_status: 'rejected', remarks_required: true, percentage: null },
  ] }
  detailApi([
    ['PUT', '/interview/', (body) => ({ body: DETAIL({ ...atDac, interview_date: body.interview_date,
      interview_remarks: body.interview_remarks, interview_recorded_by: 'Test User' }) })],
    ['POST', '/actions/', () => ({ body: { id: 7, status: 'awaiting_forwarding', status_label: 'Awaiting forwarding',
      left_queue: true, available_actions: [] } })],
  ], () => DETAIL(atDac))
  renderAt('/review/7', 'dac_member')
  const form = await screen.findByRole('form', { name: 'DAC interview' })
  await userEvent.type(within(form).getByLabelText('Interview remarks'), 'Father is a clerk.')
  await userEvent.click(within(form).getByRole('button', { name: 'Save interview' }))
  expect(await screen.findByText('Interview saved.')).toBeInTheDocument()
  expect(calls.find((c) => c.method === 'PUT').body.interview_remarks).toBe('Father is a clerk.')

  await userEvent.type(screen.getByLabelText(/Scholarship percentage/), '60')
  await userEvent.click(screen.getByRole('button', { name: 'Shortlist' }))
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ action: 'shortlist', remarks: '', percentage: 60 })
  expect(await screen.findByText(/is now at "Awaiting forwarding" and has left your queue/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Back to DAC review queue' })).toHaveAttribute('href', '/review')
})

test('Placement forwards all shortlisted cases after confirming', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  mockApi([...LISTS,
    ['GET', '/review/applications/', () => ({ body: { count: 0, next: null, previous: null, results: [] } })],
    ['POST', '/forward-all/', () => ({ body: { forwarded: [7, 8], skipped: [] } })],
  ])
  renderAt('/review')
  await userEvent.click(await screen.findByRole('button', { name: 'Forward all shortlisted to the Director' }))
  expect(await screen.findByText('Forwarded 2 cases to the Director.')).toBeInTheDocument()
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ confirm: true, cycle: null })
})

test('the DAC sees its own queue without Placement filters or forwarding', async () => {
  mockApi([...LISTS, ['GET', '/review/applications/', () => ({ body: { count: 1, next: null, previous: null,
    results: [ROW({ status: 'dac_review' })] } })]])
  renderAt('/review', 'dac_member')
  expect(await screen.findByRole('heading', { name: 'DAC review queue' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Status')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Department')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Forward all/ })).not.toBeInTheDocument()
})
