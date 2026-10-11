# ASIMS

Automated Scholarship and Internship Management System, Air University Multan Campus (FYP).

## Stack
- Backend: Django 5 + Django REST Framework, JWT (SimpleJWT), PostgreSQL
- Frontend: React (Vite)
- Docs: OpenAPI at `/api/v1/docs/`

## Layout
- `backend/` Django project (`config/`) and apps in `backend/apps/`
- `frontend/` React app
- `.github/workflows/ci.yml` runs backend and frontend tests on every push

## Run the backend
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then set DB_PASSWORD
python manage.py migrate
python manage.py runserver
```
Test: `pytest -q`

## Run the frontend
```
cd frontend
npm install
npm run dev      # http://localhost:5173
```
Test: `npm test`

## Development workflow
One branch per phase (`phase-N-name`). A phase is merged into `main` and tagged only after its tests pass.
