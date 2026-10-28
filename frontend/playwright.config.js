import { defineConfig, devices } from '@playwright/test'

// End-to-end test of the scholarship approval chain in a real browser (npm run e2e).
// It starts its own backend (port 8001, throwaway database) and frontend (port 5174).
export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5174',
    viewport: { width: 1280, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } } }],
  webServer: [
    {
      command: 'node e2e/start-backend.mjs',
      url: 'http://127.0.0.1:8001/api/v1/health/',
      timeout: 180_000,
      reuseExistingServer: false,
    },
    {
      command: 'npx vite --port 5174 --strictPort',
      url: 'http://localhost:5174',
      env: { API_TARGET: 'http://127.0.0.1:8001' },
      timeout: 60_000,
      reuseExistingServer: false,
    },
  ],
})
