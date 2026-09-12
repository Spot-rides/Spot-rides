# Spot Rides — Tech Stack

## Frontend (`frontend/`)
- **Framework**: Expo (React Native) — blank template
- **Runtime**: Node 24 / npm 11
- **Entry point**: `frontend/App.js`
- **Run commands**:
  - `npm run android` — Android emulator / device
  - `npm run ios` — iOS (macOS only)
  - `npm run web` — Browser via Expo Web

## Backend (`backend/`)
- **Framework**: Django 6.1 + Django REST Framework 3.18
- **Python**: 3.14 (venv at `backend/venv/`)
- **CORS**: `django-cors-headers` — `CORS_ALLOW_ALL_ORIGINS = True` (dev only)
- **DB**: PostgreSQL via `psycopg2-binary`; config via `.env` (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`)
- **Config**: `python-decouple` reads `.env`; copy `backend/.env.example` → `backend/.env` and fill in credentials
- **Project package**: `config/` (settings, urls, wsgi, asgi)
- **Health endpoint**: `GET /api/health/` → `{"status": "ok", "service": "spot-rides-api"}`
- **Run command**: `backend\venv\Scripts\python manage.py runserver`
- **Dependencies**: `backend/requirements.txt`

## Conventions
- All REST views live under `api/` URL prefix
- Add new Django apps with `python manage.py startapp <name>` inside `backend/`
- Expo screens go in `frontend/screens/`, shared components in `frontend/components/`
