# Testing and verification

## Test layout

- `tests/unit/` contains backend, image-processing, model, registry, and inference tests.
- `tests/integration/` contains FastAPI authentication, patient/case, upload, prediction, review, and explanation tests.
- `tests/e2e/` contains one Python workflow test. It is not a browser-driven Playwright/Cypress suite.
- Frontend Vitest covers registration payload/accessibility, case service URL behavior, and case-store behavior. No browser-driven Playwright/Cypress suite exists.

The checked-in registry has no active model version and there are no verified evaluation datasets. Prediction tests assert explicit unavailability rather than substitute random initialized models. Explanation and prediction-dependent review integration tests skip because promoted, present checkpoints are not available; local ignored artifacts do not count as verified model evidence.

## Commands

Run from the repository root after installing Python dependencies:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The pytest configuration points to `tests/` and adds `backend/` to the import path. Test dependencies are declared in the backend development requirements; ML dependencies are declared separately under `ml/requirements.txt`.

For the frontend, from `frontend/`:

```bash
npm ci
npm run build
npm run lint
npm run test -- --run
```

The frontend Vitest suite contains 12 tests across 6 files, including a stale-output/report-preview component check. Production configuration checks are in `tests/unit/test_config.py` and include credential-redaction coverage. `tests/unit/test_repositories.py` checks that audit persistence drops diagnosis text, clinical notes, case numbers, and unknown detail values. `tests/integration/test_case_report_api.py` checks draft/current/stale report behavior, ownership, identifier omission, and preview audit events.

## Verification in the audit environment

| Command/check | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -q` | **Passed:** 177 passed, 14 skipped, 0 failed (191 collected); 30 warnings. Skips are model-dependent and require unavailable verified artifacts. |
| `cd frontend && npm run lint` | **Passed.** |
| `cd frontend && npm run build` | **Passed:** TypeScript and Vite build. Vite reports a roughly 832 kB minified JS chunk. |
| `cd frontend && npm test -- --run` | **Passed:** 6 files, 12 tests. |
| Focused Ruff `E9,F` checks on `backend/app/config.py` and `tests/unit/test_config.py` | **Passed.** Broad Ruff remains unresolved. |
| Mypy | **Unresolved:** previous run failed parsing installed NumPy stubs against the configured Python target; not rerun. |
| Docker Compose build/start | **Blocked:** Docker Desktop engine pipe unavailable; no containers built or started. |
| Alembic migrations | **Passed:** new revisions were applied/checked by migration tests against disposable SQLite databases; PostgreSQL migration execution is unverified. |
| Production settings | **Passed:** all 16 focused configuration tests pass, including checks that rejected database credentials are not included in the error message and that an empty URL derives the Compose database URL from components. Environment-variable loading was also smoke-checked with `_env_file=None`. |
| Compose YAML | **Passed:** parsed statically with PyYAML. Compose build/start remains unverified because Docker Desktop is unavailable. |

Tests did not use the local `.env`, local `medfusion.db`, ignored model artifacts, or patient records. Both development servers are stopped.

## Coverage and CI

No coverage percentage is claimed. No checked-in GitHub Actions workflow was found in the inspected repository. Add CI for backend tests/lint, frontend build/lint/tests, migration checks, and supported Docker builds after the local commands are reproducible.
