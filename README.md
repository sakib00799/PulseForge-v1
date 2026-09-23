# PulseForge

PulseForge is a multi-tenant incident intelligence dashboard. Teams register services, issue scoped ingestion keys, send telemetry events, and track incidents created from repeated failures. The repository contains a FastAPI API, a Next.js frontend, PostgreSQL migrations, tests, and a Docker Compose setup.

## Features

- Account registration and sign-in, access tokens, rotating refresh sessions, password change/reset, and session revocation.
- Organizations with owner/admin/engineer/viewer permissions and tenant-scoped services, members, incidents, and audit logs.
- Scoped API keys for event ingestion; repeated matching failures can open an incident that can be acknowledged or resolved.
- Request IDs, structured API errors, rate limits, audit logging, and an active-incident uniqueness constraint.
- Responsive dashboard for services, events, incidents, team management, security, and audit history, with light/dark themes.

## Stack and layout

| Area | Technology | Location |
| --- | --- | --- |
| API | Python 3.11+, FastAPI, SQLAlchemy, Pydantic | `backend/app/` |
| Migrations and tests | Alembic, pytest | `backend/alembic/`, `backend/tests/` |
| Web app | Next.js 16, React 19, TypeScript | `frontend/app/`, `frontend/components/` |
| Database | PostgreSQL 16 | `docker-compose.yml` |
| Local orchestration | Docker Compose | `docker-compose.yml` |

The Next.js app sends `/api/v1/*` requests to FastAPI through the rewrite in `frontend/next.config.ts`. Its default backend target is `http://127.0.0.1:8001`; Compose uses `http://backend:8000` inside its network.

## Prerequisites

- Recommended: Docker with Compose (`docker compose`).
- For running without application containers: Python **3.11 or newer**, Node.js **22** with npm, and a PostgreSQL instance (the Compose database can be used).
- Ports **3000** (web), **8001** (API), and **5434** (host-facing PostgreSQL) must be free for the documented setup. Change the port mappings and URLs if they are occupied.

## Quick start: Docker Compose

Run these commands from the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

On macOS/Linux, use `cp .env.example .env` instead. The API container runs `alembic upgrade head` automatically before starting. Open:

- Web app: <http://localhost:3000>
- FastAPI Swagger UI: <http://localhost:8001/docs>
- API liveness: <http://localhost:8001/api/v1/health>
- API database readiness: <http://localhost:8001/api/v1/health/ready>

Create an account in the web app, create an organization, then register a service. To stop the containers without deleting database data, run `docker compose down`.

**Development only:** the checked-in examples use dummy credentials and development mode. Before any deployment, supply unique secrets, production-safe settings, HTTPS, and an external PostgreSQL host; do not deploy this Compose file unchanged.

## Run API and frontend locally

You can run only PostgreSQL in Docker, then run both applications on your host. First copy the root example and start the database:

```powershell
Copy-Item .env.example .env
docker compose up -d postgres
```

In a PowerShell terminal:

```powershell
Set-Location backend
Copy-Item .env.example .env
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

Use `python3 -m venv .venv` and `source .venv/bin/activate` on macOS/Linux. If you use Python 3.12 instead, use that interpreter when creating the environment. Keep the `backend/.env` database user/password and port in sync with the root `.env` PostgreSQL settings. The provided examples already match.

In a separate terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open <http://localhost:3000>. The Next.js rewrite targets port 8001 by default. If your API is elsewhere, set `BACKEND_URL` for the frontend process before starting or building Next.js. Leave `NEXT_PUBLIC_API_BASE_URL` unset for the same-origin rewrite; it is only needed when calling a separate public API directly.

## Environment variables

Copy examples; never commit the resulting `.env` files.

| File | Purpose |
| --- | --- |
| `.env.example` | Root Compose variables for PostgreSQL and development JWT/API-key secrets. Copy to `.env`. |
| `backend/.env.example` | Settings for FastAPI/Alembic when run outside Docker. Copy to `backend/.env`. |

Important backend settings include `APP_ENV`, `APP_DEBUG`, `DATABASE_URL`, `CORS_ORIGINS`, `JWT_SECRET_KEY`, `API_KEY_PEPPER`, token expiry settings, and `REFRESH_COOKIE_NAME`. The frontend normally needs no `.env`. `BACKEND_URL` controls its server-side API rewrite. Production configuration validation rejects development placeholders, debug mode, wildcard CORS, and a local database URL. Generate independent random secrets for JWT signing and API-key hashing and keep them outside the repository. If a database password contains URL-reserved characters, URL-encode it in `DATABASE_URL`.

## Useful commands

Run from `backend/` with the virtual environment active:

```powershell
alembic upgrade head
pytest
```

Run from `frontend/`:

```powershell
npm run typecheck
npm run build
npm run start
```

`npm run start` serves a completed production build. The frontend Dockerfile builds and starts that version automatically. API documentation is available at `/docs` on the API port. To send a demo incident from the UI, create a service and an API key, then use **Send 5 demo failures**. The backend also has `scripts/generate_demo_events.py`, which takes `--api-key` and optionally `--base-url`; do not paste real keys into shared logs or issue trackers.

## Notes and troubleshooting

- If migrations or `/health/ready` fail, confirm PostgreSQL is running and `DATABASE_URL` matches its host port, database, user, and password. If an old `postgres_data` volume was initialized with a different password, changing `.env` alone will not reset that database user.
- If the web app cannot reach the API, confirm `http://localhost:8001/api/v1/health` works and that the frontend's `BACKEND_URL` points to it. Inside Compose, the backend service is reached as `http://backend:8000`.
- `POST /api/v1/auth/forgot-password` returns a reset token only in development/test responses. Email delivery is **not** implemented; configure a secure delivery mechanism before offering password recovery in production.
- Rate limiting is in-process memory, so it does not coordinate across multiple API replicas. A shared store is needed for multi-instance deployments.
- `backend/.env`, dependency folders, builds, local databases, and cache files are excluded by `.gitignore`. Review staged files before every commit.

The original design notes are in [`PulseForge_System_Design_Project.md`](PulseForge_System_Design_Project.md). They may describe planned capabilities beyond the current implementation; this README documents the runnable project.
