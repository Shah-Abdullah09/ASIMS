import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App.jsx'
import { AuthProvider } from '../AuthContext.jsx'

const page = (results) => ({ count: results.length, next: null, previous: null, results })
const USERS = [
  { id: 2, email: 'sana@au.edu.pk', full_name: 'Sana Placement', role: 'placement_officer', department: null, is_active: true },
  { id: 3, email: 'dac@au.edu.pk', full_name: 'Dr Kamran', role: 'dac_member', department: 5, is_active: true },
  { id: 4, email: 'ali@students.au.edu.pk', full_name: 'Ali Khan', role: 'student', department: 5, program: 7, is_active: true },
]
const PROGRAMS = [
  { id: 7, department: 5, department_name: 'Computer Science', name: 'BS Computer Science', is_active: true },
  { id: 8, department: 5, department_name: 'Computer Science', name: 'BS Artificial Intelligence', is_active: true },
]
const SUMMARY = {
  cycle: null, submitted: 4, in_progress: 1, approved: 2, rejected: 1, completed: 1, average_percentage: 50,
  total_scholarship_amount: 90000, total_semester_fees: 150000,
  by_stage: [{ stage: 'completed', label: 'Completed', count: 1 }, { stage: 'rejected', label: 'Rejected', count: 1 }],
  by_department: [{ department: 'Computer Science', submitted: 2, approved: 1, rejected: 1 }],
}

let calls
let role
function mockApi(extra = []) {
  calls = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, opts = {}) => {
    const method = opts.method || 'GET'
    const body = opts.body ? JSON.parse(opts.body) : undefined
    calls.push({ method, url, body })
    const hit = extra.find(([m, part]) => m === method && url.includes(part))
    let data = {}
    if (hit) data = hit[2](body, url)
    else if (url.includes('/auth/me/')) data = { id: 1, full_name: 'Admin', role, email: 'admin@au.edu.pk' }
    else if (url.includes('/admin/users/')) data = page(USERS)
    else if (url.includes('/admin/programs/')) data = PROGRAMS
    else if (url.includes('/admin/departments/')) data = page([{ id: 5, name: 'Computer Science', code: 'CS', is_active: true }])
    else if (url.includes('/admin/cycles/')) data = page([{ id: 1, name: 'Fall-26', opens_on: '2026-10-17', closes_on: '2026-11-02', is_active: true, applications: 7 }])
    else if (url.includes('/admin/audit-log/actions/')) data = [{ value: 'login', label: 'Logged in' }]
    else if (url.includes('/admin/audit-log/')) data = page([{ id: 9, created_at: '2026-11-03T10:00:00Z', actor: 'sana@au.edu.pk', actor_name: 'Sana Placement', actor_role: 'placement_officer', action: 'login', action_label: 'Logged in', target_type: 'accounts.user', target_id: '2', details: {}, ip_address: '127.0.0.1' }])
    else if (url.includes('/reports/scholarships/')) data = SUMMARY
    else if (url.includes('/scholarships/cycles/')) data = [{ id: 1, name: 'Fall-26' }]
    else if (url.includes('/notifications/')) data = page([])
    return { ok: true, status: method === 'POST' ? 201 : 200, json: async () => data, blob: async () => new Blob(['a,b']) }
  })
}

function renderAt(path, as = 'administrator') {
  role = as
  localStorage.setItem('asims_tokens', JSON.stringify({ access: 'a', refresh: 'r' }))
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>)
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

test('the Administrator adds a staff account by invitation', async () => {
  mockApi([['POST', '/admin/users/', (body) => ({ id: 9, ...body })]])
  renderAt('/manage/users')
  const form = await screen.findByRole('form', { name: 'Add a staff account' }, { timeout: 4000 })
  await userEvent.type(within(form).getByLabelText('Email'), 'dir@au.edu.pk')
  await userEvent.type(within(form).getByLabelText('Full name'), 'Dr Director')
  await userEvent.selectOptions(within(form).getByLabelText('Role'), 'director')
  await userEvent.click(within(form).getByRole('button', { name: 'Add account' }))
  expect(await screen.findByText(/invitation to set a password was emailed to dir@au.edu.pk/)).toBeInTheDocument()
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ email: 'dir@au.edu.pk', full_name: 'Dr Director',
    role: 'director', department: null })
  expect(screen.getByText('Sana Placement')).toBeInTheDocument()
})

test('a user can be edited and sent a new invitation', async () => {
  mockApi([
    ['PATCH', '/admin/users/2/', (body) => ({ ...USERS[0], ...body })],
    ['POST', '/admin/users/2/invite/', () => ({ detail: 'Invitation sent to sana@au.edu.pk.' })],
  ])
  renderAt('/manage/users')
  const row = (await screen.findByText('Sana Placement', {}, { timeout: 4000 })).closest('tr')
  await userEvent.click(within(row).getByRole('button', { name: 'Send invitation' }))
  expect(await within(row).findByText('Invitation sent to sana@au.edu.pk.')).toBeInTheDocument()
  await userEvent.click(within(row).getByRole('button', { name: 'Edit' }))
  await userEvent.click(within(row).getByRole('checkbox', { name: 'Active' }))
  await userEvent.click(within(row).getByRole('button', { name: 'Save' }))
  expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ role: 'placement_officer', department: null, program: null, is_active: false })
  expect(await within(row).findByText('Deactivated')).toBeInTheDocument()
})

test("a student's program is shown and can be changed within their department", async () => {
  mockApi([['PATCH', '/admin/users/4/', (body) => ({ ...USERS[2], ...body })]])
  renderAt('/manage/users')
  const row = (await screen.findByText('Ali Khan', {}, { timeout: 4000 })).closest('tr')
  expect(within(row).getByText('BS Computer Science')).toBeInTheDocument()
  await userEvent.click(within(row).getByRole('button', { name: 'Edit' }))
  await userEvent.selectOptions(within(row).getByLabelText('Program of ali@students.au.edu.pk'), '8')
  await userEvent.click(within(row).getByRole('button', { name: 'Save' }))
  expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ role: 'student', department: 5, program: 8, is_active: true })
  expect(await within(row).findByText('BS Artificial Intelligence')).toBeInTheDocument()
})

test('programs can be added to a department and deactivated', async () => {
  mockApi([
    ['POST', '/admin/programs/', (body) => ({ id: 9, ...body })],
    ['PATCH', '/admin/programs/7/', (body) => ({ ...PROGRAMS[0], ...body })],
  ])
  renderAt('/manage/programs')
  const form = await screen.findByRole('form', { name: 'Add a program' }, { timeout: 4000 })
  await userEvent.selectOptions(await within(form).findByLabelText('Department'), '5')
  await userEvent.type(within(form).getByLabelText('Program name'), 'BS Data Science')
  await userEvent.click(within(form).getByRole('button', { name: 'Add program' }))
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ department: 5, name: 'BS Data Science' })
  const row = screen.getByText('BS Computer Science').closest('tr')
  await userEvent.click(within(row).getByRole('button', { name: 'Deactivate' }))
  expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ is_active: false })
})

test('cycles can be opened and closed', async () => {
  mockApi([['POST', '/admin/cycles/', (body) => body], ['PATCH', '/admin/cycles/1/', (body) => body]])
  renderAt('/manage/cycles')
  const row = (await screen.findByText('Fall-26', {}, { timeout: 4000 })).closest('tr')
  expect(within(row).queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument() // it has applications
  await userEvent.click(within(row).getByRole('button', { name: 'Close' }))
  expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ is_active: false })
  const form = screen.getByRole('form', { name: 'Open a new cycle' })
  await userEvent.type(within(form).getByLabelText('Name'), 'Spring-27')
  await userEvent.type(within(form).getByLabelText('Opens on'), '2027-02-01')
  await userEvent.type(within(form).getByLabelText('Closes on'), '2027-03-01')
  await userEvent.click(within(form).getByRole('button', { name: 'Add cycle' }))
  expect(calls.find((c) => c.method === 'POST').body).toEqual({ name: 'Spring-27', opens_on: '2027-02-01', closes_on: '2027-03-01' })
})

test('the audit log can be filtered by action', async () => {
  mockApi()
  renderAt('/manage/audit')
  expect(await screen.findByText('Logged in', { selector: 'td' }, { timeout: 4000 })).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Action'), 'login')
  expect(calls.some((c) => c.url.includes('/admin/audit-log/?action=login'))).toBe(true)
})

test('reports show the headline figures and placement can download the CSV', async () => {
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  mockApi()
  renderAt('/reports', 'placement_officer')
  const tiles = await screen.findByRole('list', { name: 'Headline figures' }, { timeout: 4000 })
  expect(within(tiles).getByText('Rs. 90,000')).toBeInTheDocument()
  expect(within(tiles).getByText('50%')).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: 'Computer Science' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Download CSV (Excel)' }))
  expect(calls.some((c) => c.url.includes('/reports/scholarships.csv'))).toBe(true)
  expect(click).toHaveBeenCalled()
})

test('approvers see reports without the CSV, and the Manage area is for the Administrator only', async () => {
  mockApi()
  renderAt('/reports', 'director')
  expect(await screen.findByRole('heading', { name: 'Scholarship reports' }, { timeout: 4000 })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Download CSV/ })).not.toBeInTheDocument()
})

test('a non-administrator is sent away from the Manage area', async () => {
  mockApi()
  renderAt('/manage/users', 'placement_officer')
  expect(await screen.findByText(/Welcome, Admin/, {}, { timeout: 4000 })).toBeInTheDocument()
  expect(calls.some((c) => c.url.includes('/admin/users/'))).toBe(false)
})
