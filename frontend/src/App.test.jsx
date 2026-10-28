import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from './App.jsx'
import { AuthProvider } from './AuthContext.jsx'

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function mockFetch(handler) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, opts) => {
    const { status = 200, body } = handler(url, opts)
    return { ok: status < 400, status, json: async () => body }
  })
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

test('anonymous visitors are sent to the login page', () => {
  renderAt('/dashboard')
  expect(screen.getByRole('heading', { name: 'ASIMS Login' })).toBeInTheDocument()
})

test('login shows the role dashboard', async () => {
  mockFetch(() => ({
    body: {
      access: 'a',
      refresh: 'r',
      user: { id: 1, email: 'dir@au.edu.pk', full_name: 'Dr Director', role: 'director' },
    },
  }))
  renderAt('/login')
  await userEvent.type(screen.getByLabelText('Email'), 'dir@au.edu.pk')
  await userEvent.type(screen.getByLabelText('Password'), 'secret')
  await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
  expect(await screen.findByText('Welcome, Dr Director')).toBeInTheDocument()
  expect(screen.getByText('Role: Director')).toBeInTheDocument()
})

test('login shows the server error for bad credentials', async () => {
  mockFetch(() => ({ status: 401, body: { detail: 'No active account found with the given credentials' } }))
  renderAt('/login')
  await userEvent.type(screen.getByLabelText('Email'), 'x@au.edu.pk')
  await userEvent.type(screen.getByLabelText('Password'), 'bad')
  await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('No active account found')
})

test('registration shows the server error', async () => {
  mockFetch((url) =>
    url.includes('/departments/')
      ? { body: [{ id: 1, name: 'Computer Science', code: 'CS' }] }
      : { status: 400, body: { email: ['An account with this email already exists.'] } },
  )
  renderAt('/register')
  await userEvent.type(screen.getByLabelText('Full name'), 'Ali')
  await userEvent.type(screen.getByLabelText('Email'), 'ali@students.au.edu.pk')
  await userEvent.selectOptions(await screen.findByLabelText('Department'), '1')
  await userEvent.type(screen.getByLabelText('Password'), 'Str0ng-Passw0rd!')
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('already exists')
})

test('registration success asks the student to check their email', async () => {
  mockFetch((url) =>
    url.includes('/departments/')
      ? { body: [{ id: 1, name: 'Computer Science', code: 'CS' }] }
      : { status: 201, body: { detail: 'Account created. Check your email to verify your address.' } },
  )
  renderAt('/register')
  await userEvent.type(screen.getByLabelText('Full name'), 'Ali')
  await userEvent.type(screen.getByLabelText('Email'), 'ali@students.au.edu.pk')
  await userEvent.selectOptions(await screen.findByLabelText('Department'), '1')
  await userEvent.type(screen.getByLabelText('Password'), 'Str0ng-Passw0rd!')
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  expect(await screen.findByText(/Check your email to verify/)).toBeInTheDocument()
})

test('verify-email page reports the result', async () => {
  mockFetch(() => ({ body: { detail: 'Email verified. You can now log in.' } }))
  renderAt('/verify-email?token=abc')
  expect(await screen.findByText('Email verified. You can now log in.')).toBeInTheDocument()
})

// ---------- passwords ----------

function requestsTo(part) {
  return globalThis.fetch.mock.calls.filter(([url]) => url.includes(part)).map(([, opts]) => JSON.parse(opts.body))
}

test('forgot password: link from the login page, same reply for any email', async () => {
  mockFetch(() => ({ body: { detail: 'If an account exists for this email, a link to reset the password has been sent.' } }))
  renderAt('/login')
  await userEvent.click(screen.getByRole('link', { name: 'Forgot password?' }))
  await userEvent.type(screen.getByLabelText('Email'), 'ali@gmail.com')
  await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }))
  expect(await screen.findByRole('status')).toHaveTextContent('If an account exists for this email')
  expect(requestsTo('/auth/password/forgot/')).toEqual([{ email: 'ali@gmail.com' }])
})

test('reset link: passwords must match, server rules are shown, then success', async () => {
  let attempt = 0
  mockFetch(() => (++attempt === 1
    ? { status: 400, body: { new_password: ['This password is too common.'] } }
    : { body: { detail: 'Your password has been set. You can now log in.' } }))
  renderAt('/reset-password?token=abc123')
  await userEvent.type(screen.getByLabelText('New password'), 'password1')
  await userEvent.type(screen.getByLabelText('Repeat the new password'), 'password2')
  await userEvent.click(screen.getByRole('button', { name: 'Set password' }))
  expect(screen.getByRole('alert')).toHaveTextContent('do not match')
  expect(globalThis.fetch).not.toHaveBeenCalled()

  await userEvent.clear(screen.getByLabelText('Repeat the new password'))
  await userEvent.type(screen.getByLabelText('Repeat the new password'), 'password1')
  await userEvent.click(screen.getByRole('button', { name: 'Set password' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('This password is too common.')
  await userEvent.click(screen.getByRole('button', { name: 'Set password' }))
  expect(await screen.findByRole('status')).toHaveTextContent('You can now log in.')
  expect(requestsTo('/auth/password/reset/')[0]).toEqual({ token: 'abc123', new_password: 'password1' })
})

test('reset page without a token asks for a new link', () => {
  renderAt('/reset-password')
  expect(screen.getByRole('link', { name: 'Ask for a new link' })).toHaveAttribute('href', '/forgot-password')
})

test('a logged-in user changes their password from the dashboard', async () => {
  localStorage.setItem('asims_tokens', JSON.stringify({ access: 'a', refresh: 'r' }))
  mockFetch((url) => {
    if (url.includes('/auth/me/')) return { body: { id: 1, email: 'po@au.edu.pk', full_name: 'Sana', role: 'placement_officer' } }
    const body = JSON.parse(globalThis.fetch.mock.calls.at(-1)[1].body)
    return body.current_password === 'wrong'
      ? { status: 400, body: { current_password: ['Your current password is not correct.'] } }
      : { body: { detail: 'Your password has been changed.' } }
  })
  renderAt('/dashboard')
  await userEvent.click(await screen.findByRole('link', { name: 'Change password' }))
  await userEvent.type(screen.getByLabelText('Current password'), 'wrong')
  await userEvent.type(screen.getByLabelText('New password'), 'An0ther-Str0ng-One!')
  await userEvent.type(screen.getByLabelText('Repeat the new password'), 'An0ther-Str0ng-One!')
  await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Your current password is not correct.')
  await userEvent.clear(screen.getByLabelText('Current password'))
  await userEvent.type(screen.getByLabelText('Current password'), 'Str0ng-Passw0rd!')  // new password kept
  await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Your password has been changed.')
  expect(requestsTo('/auth/password/change/').at(-1)).toEqual(
    { current_password: 'Str0ng-Passw0rd!', new_password: 'An0ther-Str0ng-One!' })
})
