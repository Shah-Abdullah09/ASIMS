import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Forward API calls to the Django backend (the end-to-end test points this at its own backend)
    proxy: { '/api': process.env.API_TARGET || 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    globals: true,
    exclude: ['node_modules/**', 'e2e/**'],
  },
})
