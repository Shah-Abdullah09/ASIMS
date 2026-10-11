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

test('registration shows the email domain error from the API', async () => {
  mockFetch((url) =>
    url.includes('/departments/')
      ? { body: [{ id: 1, name: 'Computer Science', code: 'CS' }] }
      : { status: 400, body: { email: ['Students must register with an @students.au.edu.pk email address.'] } },
  )
  renderAt('/register')
  await userEvent.type(screen.getByLabelText('Full name'), 'Ali')
  await userEvent.type(screen.getByLabelText('University email'), 'ali@gmail.com')
  await userEvent.selectOptions(await screen.findByLabelText('Department'), '1')
  await userEvent.type(screen.getByLabelText('Password'), 'Str0ng-Passw0rd!')
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('@students.au.edu.pk')
})

test('registration success asks the student to check their email', async () => {
  mockFetch((url) =>
    url.includes('/departments/')
      ? { body: [{ id: 1, name: 'Computer Science', code: 'CS' }] }
      : { status: 201, body: { detail: 'Account created. Check your email to verify your address.' } },
  )
  renderAt('/register')
  await userEvent.type(screen.getByLabelText('Full name'), 'Ali')
  await userEvent.type(screen.getByLabelText('University email'), 'ali@students.au.edu.pk')
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
