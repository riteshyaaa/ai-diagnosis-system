# Local setup and deployment status

> These instructions describe the repository's current development layout; they have not been successfully executed in the audit environment. This is not a production deployment guide. No model checkpoints are included, so prediction endpoints remain unavailable.

## Prerequisites

- Docker Engine with Compose v2 for the container setup.
- Python 3.11+ for the backend/ML packages.
- Node.js 20+ for the frontend.
- PostgreSQL 16+ if running the backend outside Docker.

## Docker Compose (local development)

From the repository root:

```bash
git clone https://github.com/riteshyaaa/ai-diagnosis-system.git
cd ai-diagnosis-system
cp .env.example .env
```

Replace `POSTGRES_PASSWORD` and `SECRET_KEY` in `.env`; do not use the example placeholders for a shared deployment. Validate and start:

For production mode, also set `APP_ENV=production`, `DEBUG=false`, an explicit HTTPS `CORS_ORIGINS` list, a non-default `POSTGRES_USER` of at least 8 characters, a database password of at least 16 characters, and a non-placeholder `SECRET_KEY` of at least 32 characters. Production startup validates these settings, but this does not replace secret management, TLS, network controls, or an operational security review. The Compose backend intentionally clears `DATABASE_URL` so it builds a URL from `POSTGRES_*` values and reaches the database at the Compose hostname `db`; host development can continue using the example's `localhost` URL.

```bash
docker compose --env-file .env -f docker/docker-compose.yml config
docker compose --env-file .env -f docker/docker-compose.yml up --build -d
```

Local endpoints, if the services start:

- Frontend: `http://localhost/`
- Backend health: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs` only when debug mode exposes it

Compose maps the database and backend ports to the host by default. Do not expose those mappings on an untrusted network. The health endpoint is a basic process response; it does not verify database or model readiness.

## Local development without Docker

From the repository root, configure `.env` with a reachable local PostgreSQL service and development-only secrets:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements-dev.txt -r ml/requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

The frontend's development API base URL is configured in `.env.example`. Demo accounts are optional and must remain disabled outside local development.

## Database and files

The Compose file defines PostgreSQL and persistent volumes for database, uploaded files, and logs. The backend container applies Alembic migrations before starting, and application startup checks that the database is at the current Alembic head. The migrations are additive in this implementation pass, but PostgreSQL execution has not been exercised in this environment. Review migrations and take a restorable backup before upgrading any database with records you need to keep. Define tested recovery, retention, and filesystem-permission procedures before deployment.

## Production readiness checklist

Production operation is **blocked** until, at minimum:

1. Production settings reject debug mode, demo users, short or placeholder signing keys, local/non-PostgreSQL database URLs, weak/default database credentials, and non-HTTPS CORS origins. This validation has unit coverage; PostgreSQL startup has not been verified here.
2. Database/backend ports are private; HTTPS, reverse-proxy body/time/concurrency limits, and monitoring are configured.
3. Record-level and institution-level access control is specified and verified.
4. Database migrations, backups/recovery, upload retention, audit design, and operational runbooks are implemented and tested.
5. CI and local tests/builds pass.
6. Any model is independently verified for artifact integrity, preprocessing compatibility, data provenance, evaluation, and intended use.

No deployment or clinical-validation claim is made. See `IMPLEMENTATION_AUDIT.md`, `SECURITY.md`, and `MODEL_CARD.md`.
