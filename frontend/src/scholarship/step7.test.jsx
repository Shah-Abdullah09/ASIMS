import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import DocumentsPage from './DocumentsPage.jsx'
import Form2Page from './Form2Page.jsx'
import StatusPage from './StatusPage.jsx'

const SUMMARY = { total_monthly_income: 0, net_monthly_disposable: 0 }
const app = (over = {}) => ({
  id: 7, cycle: { id: 1, name: 'Fall-26' }, status: 'draft', is_editable: true, submitted_at: null,
  updated_at: '2026-10-22T10:00:00Z', review_remarks: '', status_history: [], summary: SUMMARY,
  completion: { form_submitted: false, declarations_required: 1, scans_uploaded: false, physical_copies_received: false, complete: false },
  ...over,
})
const READINESS = { ready: false, sections: {}, missing_documents: ['domicile'], problems: [] }

const slot = (over) => ({
  slot: 'domicile', label: '2. Domicile of Student', kind: 'always', required: true, reason: 'Required for every applicant.',
  max_files: 5, files: [], missing: true, ...over,
})
const FILE = { id: 11, slot: 'domicile', original_name: 'domicile.pdf', content_type: 'application/pdf', size: 204800,
  uploaded_by: 'Ali Khan', uploaded_at: '2026-10-22T10:00:00Z', download_url: '/api/v1/scholarships/documents/11/download/' }

let calls
function mockApi(routes) {
  calls = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, opts = {}) => {
    const method = opts.method || 'GET'
    const body = opts.body instanceof FormData ? opts.body : opts.body ? JSON.parse(opts.body) : undefined
    calls.push({ method, url, body, headers: opts.headers })
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
        <Route path="/scholarships/:id/documents" element={<DocumentsPage />} />
        <Route path="/scholarships/:id/form2" element={<Form2Page />} />
        <Route path="/scholarships/:id/status" element={<StatusPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => vi.restoreAllMocks())

// ---------- documents ----------

function documentsApi(checklist, extra = []) {
  mockApi([
    ...extra,
    ['GET', '/readiness/', () => ({ body: READINESS })],
    ['GET', '/applications/7/documents/', () => ({ body: checklist() })],
    ['GET', '/scholarships/applications/7/', () => ({ body: app() })],
  ])
}

test('documents page shows each slot with its rule and what is missing', async () => {
  documentsApi(() => [
    slot(),
    slot({ slot: 'rent_agreement', label: '13. Attested Copy of House Rent Agreement', kind: 'conditional', required: true,
      reason: 'Required because your house is rented.' }),
    slot({ slot: 'hostel_proof', label: '14. Hostel Fee Slip', kind: 'optional', required: false, missing: false,
      reason: 'Optional. Upload if it applies to you.' }),
  ])
  renderAt('/scholarships/7/documents')
  expect(await screen.findByText('2 required documents still missing.')).toBeInTheDocument()
  const rent = screen.getByRole('listitem', { name: '13. Attested Copy of House Rent Agreement' })
  expect(within(rent).getByText('Required because your house is rented.')).toBeInTheDocument()
  expect(within(rent).getByText('Required for you · missing')).toBeInTheDocument()

  await userEvent.click(screen.getByLabelText('Show only missing documents'))
  expect(screen.queryByRole('listitem', { name: '14. Hostel Fee Slip' })).not.toBeInTheDocument()
})

test('uploading a file sends the slot and file, then shows it', async () => {
  let uploaded = false
  documentsApi(() => [uploaded ? slot({ files: [FILE], missing: false }) : slot()], [
    ['POST', '/applications/7/documents/', () => { uploaded = true; return { status: 201, body: FILE } }],
  ])
  renderAt('/scholarships/7/documents')
  const input = await screen.findByTestId('Upload to 2. Domicile of Student')
  await userEvent.upload(input, new File(['%PDF-1.4'], 'domicile.pdf', { type: 'application/pdf' }))

  expect(await screen.findByText('domicile.pdf')).toBeInTheDocument()
  expect(screen.getByText('All required documents are uploaded.')).toBeInTheDocument()
  const post = calls.find((c) => c.method === 'POST')
  expect(post.body.get('slot')).toBe('domicile')
  expect(post.body.get('file').name).toBe('domicile.pdf')
  expect(post.headers['Content-Type']).toBeUndefined() // the browser sets the multipart boundary
})

test('wrong type or oversized files are stopped before uploading', async () => {
  documentsApi(() => [slot()])
  renderAt('/scholarships/7/documents')
  const input = await screen.findByTestId('Upload to 2. Domicile of Student')

  await userEvent.upload(input, new File(['x'], 'letter.docx'), { applyAccept: false })
  expect(await screen.findByRole('alert')).toHaveTextContent('Only PDF, JPG or PNG files are accepted.')

  await userEvent.upload(input, new File([new Uint8Array(6 * 1024 * 1024)], 'big.pdf', { type: 'application/pdf' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The limit is 5 MB.')
  expect(calls.some((c) => c.method === 'POST')).toBe(false)
})

test('the server explains a rejected file on the slot', async () => {
  documentsApi(() => [slot()], [
    ['POST', '/documents/', () => ({ status: 400, body: { file: ['Only PDF, JPG or PNG files are accepted. This file is a different type.'] } })],
  ])
  renderAt('/scholarships/7/documents')
  await userEvent.upload(await screen.findByTestId('Upload to 2. Domicile of Student'),
    new File(['not a pdf'], 'fake.pdf', { type: 'application/pdf' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('This file is a different type.')
})

test('a file can be deleted after confirming', async () => {
  let deleted = false
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  documentsApi(() => [deleted ? slot() : slot({ files: [FILE], missing: false })], [
    ['DELETE', '/documents/11/', () => { deleted = true; return { status: 204, body: null } }],
  ])
  renderAt('/scholarships/7/documents')
  await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  expect(window.confirm).toHaveBeenCalledWith('Delete domicile.pdf?')
  expect(await screen.findByText('1 required document still missing.')).toBeInTheDocument()
})

test('after submission documents can be viewed but not changed', async () => {
  mockApi([
    ['GET', '/applications/7/documents/', () => ({ body: [slot({ files: [FILE], missing: false })] })],
    ['GET', '/scholarships/applications/7/', () => ({ body: app({ status: 'pending', is_editable: false, submitted_at: '2026-10-22T11:00:00Z' }) })],
  ])
  renderAt('/scholarships/7/documents')
  expect(await screen.findByRole('button', { name: 'View' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Upload|Add another|Delete|Replace/ })).not.toBeInTheDocument()
})

// ---------- Form 2 ----------

const DECLARATION = {
  id: 3, person: 'Father', person_name: 'Muhammad Aslam', template: 'employed', can_upload_scan: true, scan: null,
  physical_received_on: null, physical_received_by: null, is_complete: false,
  printable: {
    template: 'employed', title: 'Employed or pensioner persons',
    note: 'This declaration of income statement must be printed on a stamp paper (having value ≥ Rs.100).',
    header: 'I, Muhammad Aslam bearing CNIC # 36302-1111111-1 hereby, truthfully state the following:',
    items: ['1. I am a salaried/Retired person.', '2. The name of my Department/organization is WAPDA Multan'],
    closing: 'I have knowingly and willfully stated the above facts for the purpose of securing Air University Need Based Financial Aid ...',
    signature_line: 'Signature:          Date:',
    countersigned_by: [{ title: 'Union Councillor', fields: ['Sign & Stamp', 'Name'] }],
    student_reference: { student_name: 'Ali Khan', registration_id: '233585', application_no: 7 },
    instructions: ['Copy or print the text above onto stamp paper worth Rs.100 or more.'],
  },
}

test('Form 2 shows the official text with the student details kept outside it', async () => {
  mockApi([
    ['GET', '/readiness/', () => ({ body: READINESS })],
    ['GET', '/declarations/', () => ({ body: [DECLARATION] })],
    ['GET', '/scholarships/applications/7/', () => ({ body: app() })],
  ])
  renderAt('/scholarships/7/form2')
  const sheet = await screen.findByRole('article', { name: 'Declaration text: Employed or pensioner persons' })
  expect(within(sheet).getByText(DECLARATION.printable.header)).toBeInTheDocument()
  expect(within(sheet).getByText('2. The name of my Department/organization is WAPDA Multan')).toBeInTheDocument()
  expect(within(sheet).queryByText('233585')).not.toBeInTheDocument()
  expect(screen.getByText('233585')).toBeInTheDocument() // shown in the reference box instead
  expect(screen.getByText('Scan not uploaded yet')).toBeInTheDocument()
  expect(screen.getByText('Original not yet received by the Placement Office')).toBeInTheDocument()
})

test('Form 2 scan upload and print', async () => {
  let scanned = false
  window.print = vi.fn()
  mockApi([
    ['GET', '/readiness/', () => ({ body: READINESS })],
    ['GET', '/declarations/', () => ({ body: [scanned ? { ...DECLARATION, scan: { original_name: 'stamp.jpg', size: 300000,
      uploaded_at: '2026-10-22T12:00:00Z', download_url: '/api/v1/scholarships/declarations/3/scan/' } } : DECLARATION] })],
    ['POST', '/declarations/3/scan/', () => { scanned = true; return { body: {} } }],
    ['GET', '/scholarships/applications/7/', () => ({ body: app() })],
  ])
  renderAt('/scholarships/7/form2')
  await userEvent.upload(await screen.findByTestId('Upload scan for Father'), new File(['img'], 'stamp.jpg', { type: 'image/jpeg' }))
  expect(await screen.findByText(/Scan uploaded: stamp.jpg/)).toBeInTheDocument()
  expect(calls.find((c) => c.method === 'POST').body.get('file').name).toBe('stamp.jpg')

  await userEvent.click(screen.getByRole('button', { name: 'Print this declaration' }))
  expect(window.print).toHaveBeenCalled()
})

test('Form 2 says when no declaration is needed', async () => {
  mockApi([
    ['GET', '/readiness/', () => ({ body: READINESS })],
    ['GET', '/declarations/', () => ({ body: [] })],
    ['GET', '/scholarships/applications/7/', () => ({ body: app() })],
  ])
  renderAt('/scholarships/7/form2')
  expect(await screen.findByText(/No declaration is needed/)).toBeInTheDocument()
})

test('once the office has the original, the scan is locked', async () => {
  mockApi([
    ['GET', '/declarations/', () => ({ body: [{ ...DECLARATION, can_upload_scan: false, physical_received_on: '2026-10-21',
      physical_received_by: 'Sana Placement', scan: { original_name: 'stamp.jpg', size: 1000, uploaded_at: '2026-10-20T10:00:00Z',
        download_url: '/x' } }] })],
    ['GET', '/scholarships/applications/7/', () => ({ body: app({ status: 'pending', is_editable: false, submitted_at: '2026-10-20T09:00:00Z' }) })],
  ])
  renderAt('/scholarships/7/form2')
  expect(await screen.findByText(/Original received by the Placement Office on 21 Oct 2026 \(Sana Placement\)/)).toBeInTheDocument()
  expect(screen.getByText(/scan can no longer be changed/)).toBeInTheDocument()
  expect(screen.queryByTestId('Upload scan for Father')).not.toBeInTheDocument()
})

// ---------- status ----------

test('status page shows completion, decision remarks and the timeline', async () => {
  mockApi([
    ['GET', '/scholarships/applications/7/', () => ({ body: app({
      status: 'under_review', is_editable: false, submitted_at: '2026-10-20T09:00:00Z',
      review_remarks: 'Please bring the original salary slip.',
      completion: { form_submitted: true, declarations_required: 1, scans_uploaded: true, physical_copies_received: false, complete: false },
      status_history: [
        { from_status: 'draft', to_status: 'pending', remarks: 'Submitted by the student.', changed_by: 'Ali Khan', changed_by_role: 'Student', changed_at: '2026-10-20T09:00:00Z' },
        { from_status: 'pending', to_status: 'under_review', remarks: 'Please bring the original salary slip.', changed_by: 'Sana', changed_by_role: 'Placement Officer', changed_at: '2026-10-21T09:00:00Z' },
      ],
    }) })],
  ])
  renderAt('/scholarships/7/status')
  expect(await screen.findByRole('heading', { name: 'Application status' })).toBeInTheDocument()
  expect(screen.getAllByText('Under review').length).toBeGreaterThan(0)
  expect(screen.getAllByText('Please bring the original salary slip.').length).toBe(2) // remarks box + timeline
  expect(screen.getByText('Not yet. Complete the items still pending below.')).toBeInTheDocument()
  expect(screen.getByText('Application form submitted').closest('li')).toHaveClass('done')
  expect(screen.getByText('Original stamp paper received by the Placement Office').closest('li')).toHaveClass('pending')
  expect(screen.getByText(/Placement Officer/)).toBeInTheDocument()
})
