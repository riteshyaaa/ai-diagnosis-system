# Testing and verification

## Test layout

- `tests/unit/` contains backend, image-processing, model, registry, and inference tests.
- `tests/integration/` contains FastAPI authentication, patient/case, upload, prediction, review, and explanation tests.
- `tests/e2e/` contains one Python workflow test. It is not a browser-driven Playwright/Cypress suite.
- No frontend component or browser test files were found. `frontend/package.json` defines Vitest scripts, but a script alone is not a test suite.

The repository currently contains no trained checkpoints or real evaluation datasets. Prediction/end-to-end tests assert explicit unavailability rather than substitute random initialized models. Explanation and prediction-dependent review integration tests skip with a reason until all three registered model checkpoint files exist; tests that do not require predictions remain runnable.

## Commands

Run from the repository root after installing Python dependencies:

```bash
pytest -q
```

The pytest configuration points to `tests/` and adds `backend/` to the import path. Test dependencies are declared in the backend development requirements; ML dependencies are declared separately under `ml/requirements.txt`.

For the frontend, from `frontend/`:

```bash
npm ci
npm run build
npm run lint
npm run test -- --run
```

The test command is expected to report no tests until frontend test files are added.

## Verification in the audit environment

| Command/check | Result |
|---|---|
| `pytest -q` | **Blocked before collection:** `pytest: command not found`. |
| `cd frontend && npm run build` | **Blocked before type checking:** `tsc: not found`; no `node_modules/` directory. |
| Python dependency probe | **Blocked:** FastAPI, Pydantic, SQLAlchemy, PyTorch, NumPy, and test dependencies are absent. |
| Frontend dependency probe | **Blocked:** frontend dependencies are not installed. |
| BOM-aware Python syntax check | **Passed:** 144 Python source/test files parsed without importing project dependencies. |
| Registry JSON/safety check | **Passed:** all 6 JSON files parse; the three model entries have no active checkpoint, unsupported metrics, or checksum claim. |
| Docker Compose config | **Blocked:** repository-root `.env` is absent and referenced by the Compose service configuration. |
| Docker daemon/build | **Blocked:** Docker CLI cannot connect to `/var/run/docker.sock`; no services were started. |

No tests or builds are claimed to pass in this environment. After setting up dependencies, record complete command output and fix test failures before merging.

## Coverage and CI

No coverage percentage is claimed. No checked-in GitHub Actions workflow was found in the inspected repository. Add CI for backend tests/lint, frontend build/lint/tests, migration checks, and supported Docker builds after the local commands are reproducible.
