# CLAUDE

Project-level instructions for Claude when working in this workspace.

## Stack

- **Frontend**: Expo (React Native) — `frontend/`
- **Backend**: Django 6.1 + DRF — `backend/`
- **DB**: PostgreSQL (dev credentials in `backend/.env`)

## Key Conventions

- All REST endpoints prefixed `/api/`
- Backend app modules created with `python manage.py startapp <name>`
- Expo screens in `frontend/screens/`, shared components in `frontend/components/`
- Follow schemas in `schemas/` when producing structured outputs
- Persist decisions to `docs/decisions/YYYY-MM-DD-<slug>.md`

## Agent Roles

See `AGENTS.md` for the full team roster and `.claude/agents/` for detailed personas.
