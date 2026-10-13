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

The Compose file defines PostgreSQL and persistent volumes for database, uploaded files, and logs. The application startup path currently calls SQLAlchemy `create_all()` rather than applying Alembic migrations. Do not use that behavior as a migration/rollback plan for an existing production database. Define tested backups, restoration, migrations, retention, and filesystem permissions before deployment.

## Production readiness checklist

Production operation is **blocked** until, at minimum:

1. Production settings reject default/debug secrets and unsafe configuration at startup.
2. Database/backend ports are private; HTTPS, reverse-proxy body/time/concurrency limits, and monitoring are configured.
3. Record-level and institution-level access control is specified and verified.
4. Database migrations, backups/recovery, upload retention, audit design, and operational runbooks are implemented and tested.
5. CI and local tests/builds pass.
6. Any model is independently verified for artifact integrity, preprocessing compatibility, data provenance, evaluation, and intended use.

No deployment or clinical-validation claim is made. See `IMPLEMENTATION_AUDIT.md`, `SECURITY.md`, and `MODEL_CARD.md`.
