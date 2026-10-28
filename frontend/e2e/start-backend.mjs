// Starts a throwaway Django backend for the end-to-end test: a fresh SQLite database and upload folder,
// migrated and seeded (seed_e2e), served on port 8001. Your development database is never touched.
import { execFileSync, spawn } from 'node:child_process'
import { rmSync } from 'node:fs'
import { join } from 'node:path'

const backend = join(import.meta.dirname, '..', '..', 'backend')
const python = process.env.E2E_PYTHON
  || (process.platform === 'win32' ? join(backend, '.venv', 'Scripts', 'python.exe') : 'python')
const env = {
  ...process.env,
  DB_ENGINE: 'sqlite',
  SQLITE_PATH: 'e2e.sqlite3',
  MEDIA_ROOT: 'e2e-media',
  DJANGO_ALLOWED_HOSTS: 'localhost,127.0.0.1,testserver',
  EMAIL_BACKEND: 'django.core.mail.backends.locmem.EmailBackend',
  FRONTEND_URL: 'http://localhost:5174',
}

rmSync(join(backend, 'e2e.sqlite3'), { force: true })
rmSync(join(backend, 'e2e-media'), { recursive: true, force: true })
const run = (...args) => execFileSync(python, ['manage.py', ...args], { cwd: backend, env, stdio: 'inherit' })
run('migrate', '-v', '0')
run('seed_e2e')
spawn(python, ['manage.py', 'runserver', '127.0.0.1:8001', '--noreload'], { cwd: backend, env, stdio: 'inherit' })
