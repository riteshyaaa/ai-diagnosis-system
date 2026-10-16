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

To run each backend test module in a fresh process (reducing peak ML memory use), run `python scripts/run_backend_tests.py` from the repository root. Optional file paths can be passed to run a focused subset.

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
| Verification runtime | Python 3.11.14, Node.js 20.20.0, npm 10.8.2; PyTorch CPU. Optuna was unavailable, and the managed installer could not resolve SHAP. |
| Backend suite | **Passed per file:** 28 modules, 176 passed, 19 skipped, 1 deselected, 0 failing modules. The 14 model-dependent explanation/review API tests skip because no verified model artifacts are available; 5 SHAP tests skip because SHAP is unavailable; the Optuna tuner test was deselected because Optuna is unavailable. Modules run in fresh processes to keep peak memory bounded; a single-process full-suite pass is not claimed. |
| `pytest -q --confcutdir=tests/unit tests/unit/test_init_db.py` | **Passed:** 3 tests. Covers the isolated SQLite default, migration-only behavior, explicit database URL preservation, and production-environment refusal. |
| DICOM upload API test | **Passed:** 1 test with pydicom 2.4.4 after adding a version-aware fixture call for the pydicom 2.x/3.x save API difference. |
| Database initializer smoke test | **Passed:** applied Alembic migrations twice to disposable SQLite; revision is `003_prediction_input_refs`, 10 application tables exist, and the users table remains empty. |
| `cd frontend && npm run lint` | **Passed.** |
| `cd frontend && npm run build` | **Passed:** TypeScript and Vite build. The initial JS bundle is 288.02 kB (95.37 kB gzip); the largest lazy/vendor chunk is 377.76 kB (104.13 kB gzip); CSS is 52.81 kB (8.80 kB gzip). |
| `cd frontend && npm test -- --run` | **Passed:** 6 files, 12 tests. |
| `npm audit --audit-level=low` | **Passed:** 0 vulnerabilities. |
| FastAPI startup and `/health` | **Passed:** with the disposable migrated SQLite database, Uvicorn reached “Application startup complete” and `/health` returned HTTP 200. No server was left running. |
| Windows PowerShell bootstrap | **Unverified:** updated for a Windows local database workflow, but this Linux environment has no PowerShell/Windows host to execute it. |
| PostgreSQL / Docker Compose | **Unverified:** migrations were exercised only against disposable SQLite; Docker Compose build/start was not run. |
| Ruff | **Passed for modified backend/test modules.** Repository-wide Ruff and Mypy were not run. |

The database smoke test used `/tmp/medfusion-init-test.db`; API tests use the in-memory SQLite fixture. No production database or patient records were used. The FastAPI smoke server was stopped after the health check.

## Coverage and CI

No coverage percentage is claimed. GitHub Actions is configured to run the frontend audit/lint/tests/build and the memory-bounded backend test runner plus Ruff on pushes to `main` and pull requests. Docker Compose and PostgreSQL migration checks are not part of this workflow.
