# ASIMS

Automated Scholarship and Internship Management System, Air University Multan Campus (FYP).

Release `v1.0` covers the scholarship module end to end: the Need Based Financial Grant application (Form 1) and
stamp-paper income declarations (Form 2), the approval chain (Placement Office, DAC, Director, Registrar, Vice
Chancellor), Finance's fee adjustment and the award letter, an automatic document check (OCR), notifications,
reports and the Administrator's management screens. The internship module follows in `v2.0`.

## Stack
- Backend: Django 5 + Django REST Framework, JWT (SimpleJWT), PostgreSQL; ReportLab (award letter PDF);
  Tesseract through pytesseract and pypdf (document check)
- Frontend: React (Vite), React Router
- Tests: pytest, Vitest + Testing Library, Playwright (end to end, with screenshots)
- API docs: OpenAPI at `/api/v1/docs/`

## Layout
- `backend/` Django project (`config/`) and apps in `backend/apps/`:
  `accounts` (login, roles, passwords), `scholarships` (application, chain, finance, letters, reports),
  `workflow` (reusable approval engine), `audit` (append-only audit log), `documents` (file checks, OCR),
  `notifications`
- `frontend/` React app; `frontend/e2e/` the Playwright test
- `.github/workflows/ci.yml` runs the backend, frontend and end-to-end tests on every push

## Run the backend
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then set DB_PASSWORD (see .env.example for email and production settings)
python manage.py migrate
python manage.py runserver
```
Test: `pytest -q`

Optional: install Tesseract OCR (on Windows the UB Mannheim build) so the automatic document check can read photos
and scans; without it, PDFs with text are still checked.

Emails print in the backend console unless `EMAIL_HOST` is set in `.env`. For testing,
`python manage.py password_link <email>` prints a reset link (`--invite` for an invitation link).

## Run the frontend
```
cd frontend
npm install
npm run dev      # http://localhost:5173
```
Tests: `npm test` (unit), `npm run e2e` (whole approval chain in Chrome on a throwaway database; screenshots in
`frontend/e2e/screenshots/`)

## Accounts
Students register themselves and verify their email. Staff accounts are created by the Administrator under
Manage > Users (an emailed invitation lets them choose their own password).

## Production
Set `DJANGO_DEBUG=False`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`.
HTTPS redirect, secure cookies and HSTS switch on automatically; behind an HTTPS proxy also set
`DJANGO_BEHIND_PROXY=True`. Run `python manage.py check --deploy`.

## Development workflow
One branch per phase (`phase-N-name`). A phase is merged into `main` and tagged only after its tests pass on CI.
