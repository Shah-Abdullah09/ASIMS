import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App.jsx'

afterEach(() => vi.restoreAllMocks())

test('shows the API status returned by the health endpoint', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ status: 'ok' }),
  })
  render(<App />)
  expect(screen.getByText('ASIMS')).toBeInTheDocument()
  expect(await screen.findByText('API status: ok')).toBeInTheDocument()
})

test('shows unreachable when the API cannot be contacted', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('down'))
  render(<App />)
  expect(await screen.findByText('API status: unreachable')).toBeInTheDocument()
})
