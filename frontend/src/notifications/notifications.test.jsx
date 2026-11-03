import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App.jsx'
import { AuthProvider } from '../AuthContext.jsx'

const NOTES = [
  { id: 2, title: 'Application 7 is waiting for you (DAC review)', body: 'Ali Khan has reached DAC review.',
    link: '/review', created_at: '2026-11-03T10:00:00Z', read_at: null },
  { id: 1, title: 'Welcome', body: '', link: '', created_at: '2026-11-02T10:00:00Z', read_at: '2026-11-02T11:00:00Z' },
]

let calls
function mockApi({ unread = 1, emailOn = true } = {}) {
  calls = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, opts = {}) => {
    const method = opts.method || 'GET'
    calls.push({ method, url, body: opts.body ? JSON.parse(opts.body) : undefined })
    let body = {}
    if (url.includes('/auth/me/')) {
      body = { id: 1, full_name: 'Dr Kamran', role: 'dac_member', email: 'dac@au.edu.pk',
        email_notifications: method === 'PATCH' ? JSON.parse(opts.body).email_notifications : emailOn }
    } else if (url.includes('/notifications/') && method === 'GET') {
      body = { count: NOTES.length, next: null, previous: null, unread, results: NOTES }
    } else if (url.includes('/review/applications/')) {
      body = { count: 0, next: null, previous: null, results: [] }
    } else if (url.includes('/cycles/') || url.includes('/departments/')) {
      body = []
    }
    return { ok: true, status: 200, json: async () => body }
  })
}

function renderAt(path) {
  localStorage.setItem('asims_tokens', JSON.stringify({ access: 'a', refresh: 'r' }))
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>)
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

test('the header bell shows the unread count and opens the notifications', async () => {
  mockApi({ unread: 3 })
  renderAt('/dashboard')
  // Waits longer: the user loads first, then the bell asks for the count
  await userEvent.click(await screen.findByRole('link', { name: 'Notifications, 3 unread' }, { timeout: 4000 }))
  expect(await screen.findByRole('heading', { name: 'Notifications' })).toBeInTheDocument()
  expect(screen.getByText('Ali Khan has reached DAC review.')).toBeInTheDocument()
})

test('opening a notification marks it read and goes to its page', async () => {
  mockApi()
  renderAt('/notifications')
  const item = await screen.findByRole('button', { name: /waiting for you/ }, { timeout: 4000 })
  await userEvent.click(item)
  expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/notifications/2/read/'))).toBe(true)
  expect(await screen.findByRole('heading', { name: 'DAC review queue' }, { timeout: 4000 })).toBeInTheDocument()
})

test('mark all as read and switch email copies off', async () => {
  mockApi()
  renderAt('/notifications')
  await userEvent.click(await screen.findByRole('button', { name: 'Mark all as read' }, { timeout: 4000 }))
  expect(calls.some((c) => c.method === 'POST' && c.url.endsWith('/notifications/read-all/'))).toBe(true)
  const toggle = screen.getByRole('checkbox', { name: 'Also send me these by email' })
  expect(toggle).toBeChecked()
  await userEvent.click(toggle)
  expect(await screen.findByRole('status')).toHaveTextContent('Email copies are off')
  expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ email_notifications: false })
  expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(2)
})
