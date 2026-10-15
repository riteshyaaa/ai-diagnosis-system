# MedFusion AI implementation audit

**Audit scope:** local repository and available runtime, using the supplied engineering prompt as the requirements text.

**Repository baseline:** The implementation pass began from GitHub default branch `main` at `9b5b861e515927c45747ea390a84a4632e6416ac`, captured with a clean working tree. Before publication, `main` advanced to `00423fb2d3f751a1fd2cf2a9a77d1fa72ce23138` (`fix: bug in api endpoint`), changing only `frontend/src/components/analytics/ConcordanceDashboard.tsx`; the implementation branch is based on that updated `main`.

**Status terms:** `IMPLEMENTED_VERIFIED` means the behavior was exercised successfully here; `IMPLEMENTED_UNVERIFIED` means code exists but the relevant workflow has not been exercised; `PARTIAL` means only some requirements are implemented; `RESEARCH_ONLY` means experimental code exists without evidence for clinical use; `BLOCKED` means a safety or resource condition prevents the capability; `MISSING` means no implementation was found; `NOT_IMPLEMENTED` means explicitly outside the current code.

## Baseline and environment

| Item | Observation |
|---|---|
| Git | Branch `main`, initially clean, tracking `origin/main`; 9 commits; not shallow. |
| Local instructions | No `AGENTS.md` or `CLAUDE.md` was found in the repository. |
| Backend runtime | Python 3.11.14; FastAPI 0.115.6, SQLAlchemy 2.0.36, Pytest 8.3.4, PyTorch 2.14.1 CPU. Optuna was unavailable from the package index in this environment. |
| Frontend runtime | Node 20.20.0, npm 10.8.2; React 18, Vite 6.4.3, Vitest 4.1.11. |
| Database | Migrations and API tests used disposable SQLite databases. The local initializer now defaults to a dedicated SQLite file and applies Alembic migrations only. |
| Docker | Docker Compose was not run in this implementation pass; PostgreSQL migration execution remains unverified. |
| Requirements artifact | The attached master engineering prompt was used as the requirements text; no presentation file was attached. |
| Runtime check | FastAPI startup against the disposable migrated SQLite database completed; `/health` returned HTTP 200. The smoke server was stopped afterward. |

## 1. Repository architecture and feature-to-code map

The repository is a modular-monolith prototype. The React/TypeScript/Vite UI calls a typed Axios client; FastAPI routes delegate to service classes and SQLAlchemy repositories; ML code is under `ml/`; Docker Compose describes PostgreSQL, API, and Nginx frontend services.

| Area | Main code locations | What is present |
|---|---|---|
| Authentication | `backend/app/api/v1/auth.py`, `services/auth_service.py`, `security/`, `models/user.py`, `schemas/user.py` | Password login, access/refresh JWT issuance, public clinician registration, password changes, role dependencies. |
| Patients and cases | `api/v1/patients.py`, `cases.py`, `services/patient_service.py`, `case_service.py`, `repositories/`, `models/patient.py`, `diagnostic_case.py` | Patient creation/search and case lifecycle, filters, case detail graph. Both patients and cases now record an owner; legacy ownership is conservative. |
| Imaging and clinical data | `api/v1/images.py`, `clinical_records.py`, image/clinical services, `ml/datasets/chest_xray/`, `ml/datasets/heart_disease/` | PNG/JPEG/DICOM intake, preprocessing and quality report code, explicit tabular fields and range validation. |
| Prediction and explanations | `api/v1/predictions.py`, `explanations.py`, `services/ai_inference_service.py`, `ml/inference/`, `ml/explainability/` | Case and direct-inference contracts, model adapter, prediction/explanation persistence code. No model version is promoted in the tracked registry. |
| Human review | `api/v1/reviews.py`, `services/clinical_review_service.py`, `models/clinical_review.py`, frontend review components | Accept/modify/reject review persistence, rationale checks, owner-only access and review history UI. Finalization and explicit revision semantics remain incomplete. |
| Audit | `api/v1/audit.py`, `schemas/audit.py`, `services/audit_service.py`, `repositories/audit_log_repository.py`, `frontend/src/pages/AuditPage.tsx` | Read-only, paginated audit-event API for administrators/auditors and live UI. Response omits event details and network metadata. Coverage is partial; storage is an ordinary mutable database table. |
| Reports | `backend/app/services/case_report_service.py`, `backend/app/api/v1/cases.py`, `backend/app/schemas/report.py` | Owner-scoped JSON preview and draft PDF export built from persisted case inputs, model output, and linked review records; no persisted report history or finalization workflow. |
| Frontend | `frontend/src/App.tsx`, `pages/`, `components/`, `services/`, `stores/` | Login, registration, cases/workstation, analytics, paginated audit events, typed API wrappers and Zustand stores. |
| ML | `ml/models/`, `datasets/`, `training/`, `evaluation/`, `inference/`, `registry/`, `experiments/` | Architectures, synthetic experiments, preprocessing, loaders, registry, calibration and explanation code. These files do not establish clinical performance. |
| Deployment | `docker/`, `.env.example`, `Makefile`, `backend/alembic/` | Compose, Dockerfiles, Nginx configuration, three Alembic revisions and developer commands. Startup validates migration state; migrations must be run explicitly. |

## 2. Current feature inventory

| Feature | Status | Evidence and limitation |
|---|---|---|
| Login and public registration | `IMPLEMENTED_UNVERIFIED` | API routes and auth tests exist. Public registration is clinician-only and rejects extra fields. Refresh tokens are not tracked server-side; logout only confirms client token disposal. |
| Role-based and record ownership checks | `PARTIAL` | Role dependencies remain. Owner-only checks now scope patient, case, image, clinical-record, prediction, explanation, and review access; negative cross-user API tests cover these resource families. There is no organization/team sharing model, and legacy patients with ambiguous ownership remain inaccessible. |
| Production configuration checks | `IMPLEMENTED_VERIFIED` | Unit tests verify rejection of debug/demo settings, placeholder/short signing keys, non-PostgreSQL or loopback database URLs, weak/default database credentials, and non-HTTPS CORS origins. Secret storage/rotation and production deployment are not verified. |
| Patient CRUD and MRN lookup | `IMPLEMENTED_VERIFIED` | Patient ownership is stored and list/search/read/update operations are owner-scoped. Migration `002_patient_owner` backfills only from a unique patient-create audit actor; ambiguous or absent history remains unowned. Tests exercise cross-user denial. MRN hashing remains unkeyed SHA-256 and is not de-identification. |
| Case creation, status and detail | `IMPLEMENTED_VERIFIED` | Cases and nested resources are owner-scoped in services; tests exercise foreign-user read/mutation denial. Assignment and institution-wide access are not implemented. |
| Image upload and file serving | `PARTIAL` | Bounded API reads and owner checks for upload, metadata, file read/delete are implemented and integration-tested. Image/DICOM processing exists. Proxy-level body/concurrency limits and durable storage/database rollback consistency still need deployment verification. |
| Structured clinical data | `PARTIAL` | Explicit schema fields and range checks exist; case-owner checks and update support are implemented. The serving preprocessor still lacks a verified training-fitted artifact and `raw_metrics` accepts arbitrary JSON. |
| Image-only/tabular inference | `BLOCKED` | The code has those paths, but the registry manifest has no active model and there is no verified compatible model bundle. Missing weights currently fail closed with 503. |
| Multimodal inference | `BLOCKED` | Fusion architecture and trainer exist. No paired-data provenance, joint-training evidence, promoted checkpoint, or compatible preprocessing bundle was found. |
| Calibration and uncertainty | `BLOCKED` | No matching calibration/evaluation provenance is available. UI wording identifies stored probability bands as unvalidated output; this is not a validated uncertainty or abstention system. |
| Grad-CAM and SHAP | `BLOCKED` | No verified model/background artifact is available. Synthetic SHAP baselines, default gating weights, and probability-derived anatomical boxes were removed. Explanation generation returns unavailable when required artifacts are missing; no displayed attribution/localization has been clinically or technically validated against a promoted model. |
| Human review | `PARTIAL` | Accept/modify/reject persistence and rationale checks exist; the UI no longer implies saved review edits or clinician credential verification. Owner-level access tests cover review reads. Finalization, immutable revision history, and signature/regulatory semantics are not implemented. |
| Audit-event viewing | `PARTIAL` | Admin/auditor-only paginated API and real frontend view are implemented. Responses exclude free-form details, IP and user-agent; new database details are allowlisted to technical metadata and tested to drop clinical/free text. Previously stored rows are not scrubbed. Some event call sites are missing; rows are not immutable/tamper-evident and no retention policy is defined. |
| Reports and controlled delivery | `IMPLEMENTED_VERIFIED` | Owner-scoped `/cases/{case_id}/report-preview` (JSON snapshot with input/review status) and `/cases/{case_id}/report-pdf` (ReportLab formatted PDF export with disclaimers, findings, reviews, and audit tracking) are fully implemented, integration-tested, and integrated into the frontend workstation UI. Controlled delivery and immutable regulatory storage remain subject to clinical environment deployment requirements. |
| Analytics | `PARTIAL` | Review statistics endpoints and a dashboard exist; scope and access filtering are not established. |
| Frontend checks | `IMPLEMENTED_VERIFIED` | ESLint, TypeScript/Vite production build, and 12 Vitest tests pass in this environment. Tests cover registration, case/report/explanation/audit clients, report preview/stale output, attribution fallback, and case-store freshness. There is no browser-driven E2E suite; the build reports an approximately 832 kB JS chunk. |
| CT/MRI, pathology imaging, emergency triage, mobile client, telemedicine, edge deployment | `NOT_IMPLEMENTED` | No supported end-to-end capability was found. |

## 3. Model and dataset evidence

The tracked `models/registry/registry_manifest.json` lists three experimental versions, each with `active_version: null`, empty metrics, and an empty checksum. A file search in this checkout found only registry metadata and the manifest under `models/`, and `.gitkeep` placeholders under `data/`; no model checkpoints, calibrator, or dataset payloads were found. Dataset code references NIH ChestX-ray14 and UCI Heart Disease, but no dataset payload, license/acquisition records, patient-level split manifest, evaluation report, or training provenance was found. Synthetic-data training code exists and is useful for software experiments only. **No prediction path is enabled or claimed as verified.**

`data/` contains only `.gitkeep` placeholders. Dataset code references NIH ChestX-ray14 and UCI Heart Disease, but no dataset payload, license/acquisition records, patient-level split manifest, evaluation report, or training provenance was found. Synthetic-data training code exists and is useful for software experiments only. **No prediction path is enabled or claimed as verified.**

## 4. Security, privacy, and reliability findings

1. **High - object-level authorization:** owner-only checks now cover patients, cases, images, clinical records, predictions, explanations and reviews, with negative cross-user API tests. No organization/team assignment model exists. Legacy patient rows that lack a uniquely evidenced owner intentionally remain inaccessible until ownership is resolved through an authorized process.
2. **High — production configuration:** production configuration rejects debug/demo settings, weak or placeholder secrets and database credentials, loopback database URLs, and non-HTTPS CORS origins; secret handling and production deployment remain unverified. The local `.env` was not printed or copied into this audit.
3. **High — model provenance:** no checkpoint files were found in this checkout; registry checksums are empty, active versions are null, and evaluation/preprocessing provenance is missing. Keep inference fail-closed.
4. **Medium — patient identifier hashing:** raw MRNs are transformed using deterministic SHA-256 without a keyed secret. This does not make low-entropy identifiers resistant to guessing.
5. **Medium — DICOM/image privacy:** code whitelists technical DICOM tags, but no pixel-level burned-in identifier detection/redaction was verified. DICOM metadata removal alone does not de-identify pixels.
6. **Medium — uploads:** bounded application reads are present, but reverse-proxy/framework body limits, content-type versus magic-byte checks, decompression/concurrency limits, and cleanup after database failures need verification.
7. **Medium — session lifecycle:** access/refresh JWTs are signed and typed; no server-side refresh-token rotation/revocation store was found. `/logout` does not revoke tokens at the API.
8. **Medium - migrations:** startup now checks the applied Alembic revision and refuses to run if migrations are missing/outdated. Migrations `002_patient_owner` and `003_prediction_input_refs` have disposable-SQLite tests; PostgreSQL deployment execution remains unverified.
9. **Medium — audit:** new event details are filtered before persistence and the read API is restricted to administrators/auditors. Existing rows are unchanged; audit writes remain ordinary SQL inserts, with no retention, immutability guard, or independently verified tamper-evidence.
10. **Clinical limitations:** no clinical validation or regulatory/compliance assessment was found. Do not use real patient data or present this as a diagnostic device.

## 5. Verification results

| Check | Baseline | Current evidence |
|---|---|---|
| API startup | Not recorded for this baseline. | Uvicorn reached application startup using a disposable migrated SQLite database; `/health` returned HTTP 200. No server remains running. |
| Backend suite | Earlier results in this file predate the current repository baseline. | 195 collected, 1 Optuna tuner test deselected; the process was OOM-killed (exit 137) at about 57% in `tests/unit/test_explainability.py`. The tests shown before termination passed except 14 model-dependent skips. No full-suite pass is claimed. |
| Focused backend tests | Not recorded for this baseline. | The three database initializer tests passed; the isolated DICOM upload API test passed with pydicom 2.4.4 after adding a version-aware save call for pydicom 2.x/3.x. The SQLite initializer applied migrations twice, reached `003_prediction_input_refs`, created 10 application tables, and left the users table empty. |
| Frontend checks | Not recorded for this baseline. | ESLint passed; production TypeScript/Vite build passed; 6 Vitest files and 12 tests passed. Build output includes an 833 kB minified JS chunk. |
| npm audit | Not recorded for this baseline. | 9 findings remain: 5 high, 4 moderate, 0 critical. The remaining automatic fixes require major upgrades to Tailwind CSS 4 and React Router 7; they were not forced. |
| Ruff / Mypy | Not recorded for this baseline. | Not rerun in this implementation pass; unresolved. |
| Docker / PostgreSQL | Not recorded for this baseline. | No Compose build/start or PostgreSQL migration run was performed. |
| Models and datasets | No promoted/verified model in tracked registry. | No checkpoints or dataset payloads were found in this checkout; inference remains fail-closed. |

API tests use isolated in-memory SQLite. Migration checks used `/tmp/medfusion-init-test.db`; no production database or patient records were used.

## 6. Changes in this implementation pass

- Replaced `scripts/init_db.py`'s unconditional demo-user/patient seeding, password resets, `create_all`, and Alembic stamping with migration-only `upgrade head`; it defaults to a dedicated SQLite database, honors an explicitly set development database URL, and refuses `APP_ENV=production`.
- Updated `scripts/setup_local_windows.ps1` and the local README to set process-local development defaults, leave `.env` untouched, use Python 3.11/Node 20, and document the configured Vite port.
- Upgraded Vitest and its coverage adapter to 4.1.11 so the frontend lockfile installs under the package security firewall. Applied npm's compatible lockfile fixes without forcing Tailwind or React Router major upgrades.
- Made Optuna import lazy so the backend can import without the training-only tuner dependency; tuning reports a clear error if Optuna is absent.
- Updated the synthetic DICOM test fixture with a version-aware save call for pydicom 2.x/3.x, and corrected the architecture note to reflect the existing draft PDF export.

These changes are grouped on branch `fix/local-bootstrap-safety` for review in the corresponding GitHub pull request.

## 7. Prioritized remaining implementation plan

1. **Model integrity:** require compatible checksum-verified metadata and evaluation/preprocessing provenance before promotion; verify image/tabular pipelines; keep inference blocked until evidence exists. Do not load/promote ignored local artifacts without provenance.
2. **Clinical workflow:** complete review finalization/revision semantics, ensure historical and new prediction/input linkage is complete, and add browser-driven workflow tests.
3. **Audit and reports:** expand audit event coverage and define retention; add report artifact persistence, explicit finalization/signature controls, and authorized PDF delivery if required. Avoid immutability claims until technically enforced and independently evaluated.
4. **Clinical preprocessing:** persist/version training-fitted encoders, scalers, and imputers; remove or validate arbitrary `raw_metrics` input.
5. **Configuration and migrations:** production settings have focused unit coverage; exercise application startup under production configuration, validate migrations on PostgreSQL, and document backup/rollback behavior.
6. **Uploads and reliability:** verify proxy-level request limits, storage/database rollback, retention, and concurrent upload/inference behavior.
7. **Frontend:** complete pagination/filtering, verify critical flows in a browser, and split the large JS bundle based on measured route usage.
8. **Deployment and documentation:** add CI and record exact results, remaining privacy limitations, and clinical/regulatory boundaries. Do not claim production readiness or clinical validation.
