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
| Verification runtime | Python 3.11.14, Node.js 20.20.0, npm 10.8.2; PyTorch CPU. Optuna could not be installed from the available package index. |
| Backend suite | **Incomplete:** 195 collected, 1 Optuna tuner test deselected; the process was OOM-killed (exit 137) at about 57% while running `tests/unit/test_explainability.py`. Before termination, the e2e, API, migration, configuration, and dataset-loader tests shown in the output passed; 14 existing model-dependent integration tests skipped. No full-suite pass is claimed. |
| `pytest -q --confcutdir=tests/unit tests/unit/test_init_db.py` | **Passed:** 3 tests. Covers the isolated SQLite default, migration-only behavior, explicit database URL preservation, and production-environment refusal. |
| DICOM upload API test | **Passed:** 1 test with pydicom 2.4.4 after adding a version-aware fixture call for the pydicom 2.x/3.x save API difference. |
| Database initializer smoke test | **Passed:** applied Alembic migrations twice to disposable SQLite; revision is `003_prediction_input_refs`, 10 application tables exist, and the users table remains empty. |
| `cd frontend && npm run lint` | **Passed.** |
| `cd frontend && npm run build` | **Passed:** TypeScript and Vite build. Vite reports an 833 kB minified JS chunk (236.64 kB gzip). |
| `cd frontend && npm test -- --run` | **Passed:** 6 files, 12 tests. |
| `npm audit` | **9 findings:** 5 high, 4 moderate, 0 critical. Remaining automatic fixes require major upgrades to Tailwind CSS 4 and React Router 7; these were not forced. |
| FastAPI startup and `/health` | **Passed:** with the disposable migrated SQLite database, Uvicorn reached “Application startup complete” and `/health` returned HTTP 200. No server was left running. |
| Windows PowerShell bootstrap | **Unverified:** updated for a Windows local database workflow, but this Linux environment has no PowerShell/Windows host to execute it. |
| PostgreSQL / Docker Compose | **Unverified:** migrations were exercised only against disposable SQLite; Docker Compose build/start was not run. |
| Broad Ruff / Mypy | **Unresolved:** not rerun in this implementation pass. |

The database smoke test used `/tmp/medfusion-init-test.db`; API tests use the in-memory SQLite fixture. No production database or patient records were used. The FastAPI smoke server was stopped after the health check.

## Coverage and CI

No coverage percentage is claimed. No checked-in GitHub Actions workflow was found in the inspected repository. Add CI for backend tests/lint, frontend build/lint/tests, migration checks, and supported Docker builds after the local commands are reproducible.
