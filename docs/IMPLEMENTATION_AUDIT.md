# MedFusion AI implementation audit

**Audit scope:** local repository and available runtime, using the supplied engineering prompt as the requirements text.

**Repository baseline:** `main`, commit `cb6092bd41c9902fa221c1b2501881496c419b35`, captured with a clean working tree before this implementation pass. The checkout is not shallow and contains 9 commits. The presentation file titled “AI Medical Diagnosis System” was not found in the repository, adjacent project folder, Desktop, or Downloads. Presentation-specific diagrams and claims therefore remain unverified; this audit maps requirements from the supplied prompt.

**Status terms:** `IMPLEMENTED_VERIFIED` means the behavior was exercised successfully here; `IMPLEMENTED_UNVERIFIED` means code exists but the relevant workflow has not been exercised; `PARTIAL` means only some requirements are implemented; `RESEARCH_ONLY` means experimental code exists without evidence for clinical use; `BLOCKED` means a safety or resource condition prevents the capability; `MISSING` means no implementation was found; `NOT_IMPLEMENTED` means explicitly outside the current code.

## Baseline and environment

| Item | Observation |
|---|---|
| Git | Branch `main`, initially clean, tracking `origin/main`; 9 commits; not shallow. |
| Local instructions | No `AGENTS.md` or `CLAUDE.md` was found in the repository. |
| Backend runtime | Workspace virtual environment: Python 3.13.0; FastAPI 0.115.6, SQLAlchemy 2.0.36, Pytest 8.3.4, PyTorch 2.14.1 CPU, Ruff 0.8.6, Mypy 1.14.1. The system `python` resolves to 3.15.0; use `.venv` explicitly. |
| Frontend runtime | Node 24.21.0, npm 11.7.0, installed `node_modules`, lockfile present; React 18 and Vite 6. |
| Database | The local unshared `.env` selects SQLite (credentials and values are intentionally omitted). Startup checks that the database is at the current Alembic head and refuses to start otherwise. Automated API/migration tests use disposable SQLite databases. |
| Docker | Docker CLI 28.3.2 is installed, but the Docker Desktop Linux engine pipe is unavailable. Containers/builds were not run. |
| Presentation | No matching PDF/PPT/PPTX was found in the searched locations. The supplied engineering prompt is the only requirements artifact available in this workspace. |
| Runtime check | Before this pass, FastAPI `/health` and the Vite root page both returned HTTP 200. Both servers have since been stopped at the user’s request. |

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
| Reports | `backend/app/services/case_report_service.py`, `backend/app/api/v1/cases.py`, `backend/app/schemas/report.py` | Owner-scoped JSON preview built from persisted case inputs, model output, and linked review records; no PDF or persisted report artifact. |
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

The tracked `models/registry/registry_manifest.json` lists three experimental versions, each with `active_version: null`, empty metrics, empty checksum, and no preprocessing/evaluation schema. The model artifacts are absent from Git but **do exist locally as ignored files**. Each `.pt` file was opened using PyTorch `weights_only=True` and returned a dictionary; this verifies restricted deserialization only, not architecture compatibility, training, or medical validity. The local calibrator is a `.joblib` pickle and was not loaded.

| Local ignored artifact | SHA-256 | Evidence status |
|---|---|---|
| `chest_xray_vision/v1.0.0/chest_xray_vision_v1.0.0.pt` | `4445184059D34FB08DA22BDDF89494E2F8AF82C53FA378425D3654ADD6AA6A3C` | Restricted load succeeded; training and label/preprocessing provenance unknown; registry checksum blank. |
| `tabular_risk_mlp/v1.0.0/tabular_risk_mlp_v1.0.0.pt` | `312C74C8C7574F133EF2DC45D9DCC1A2878E39731FEB2150BED6FB5595157A3C` | Restricted load succeeded; training and preprocessing provenance unknown; registry checksum blank. |
| `multimodal_late_fusion/v1.0.0/multimodal_late_fusion_v1.0.0.pt` | `B6F0EE3FBF8AC201B04243E5D39F5C70DE72ABFBBFE86D85C0D2C79D1AA4D9FB` | Restricted load succeeded; paired-data/joint-training provenance unknown; registry checksum blank. |
| `tabular_risk_mlp/v1.0.0/calibrator.joblib` | `70D99045B5BF17CE75E3E38720F2A545DB64D968B79283DB597B0318D9200400` | Present locally, not tracked, not loaded; compatibility and fitting provenance unknown. |

`data/` contains only `.gitkeep` placeholders. Dataset code references NIH ChestX-ray14 and UCI Heart Disease, but no dataset payload, license/acquisition records, patient-level split manifest, evaluation report, or training provenance was found. Synthetic-data training code exists and is useful for software experiments only. **No prediction path is enabled or claimed as verified.**

## 4. Security, privacy, and reliability findings

1. **High - object-level authorization:** owner-only checks now cover patients, cases, images, clinical records, predictions, explanations and reviews, with negative cross-user API tests. No organization/team assignment model exists. Legacy patient rows that lack a uniquely evidenced owner intentionally remain inaccessible until ownership is resolved through an authorized process.
2. **High — production configuration:** production configuration rejects debug/demo settings, weak or placeholder secrets and database credentials, loopback database URLs, and non-HTTPS CORS origins; secret handling and production deployment remain unverified. The local `.env` was not printed or copied into this audit.
3. **High — model provenance:** local checkpoint files are ignored, registry hashes are empty, active versions are null, and evaluation/preprocessing provenance is missing. Keep inference fail-closed.
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
| API/frontend startup | Earlier in this session both services returned 200 at `/health` and `/`; they were stopped at the user's request. | No server is running now. Startup checks Alembic migration state and refuses to start against a missing/outdated schema. |
| Full backend suite | 141 passed, 6 failed, 14 skipped (161 collected); failures shared a missing-model error assertion. | `.venv\Scripts\python.exe -m pytest -q`: 179 passed, 14 skipped, 0 failed (193 collected), 25 warnings. Model-dependent tests skip because verified model artifacts are unavailable. |
| Frontend lint | Blocked at baseline because ESLint 9 had no flat config. | `cd frontend && npm run lint` passes. |
| Frontend build | Failed at baseline on a registration payload/type mismatch. | `cd frontend && npm run build` passes TypeScript and Vite; Vite warns the minified JS chunk is about 826 kB. |
| Frontend tests | No test files at baseline. | `cd frontend && npm test -- --run`: 6 files, 12 tests passed. |
| Ruff | Baseline broad lint reported 1,425 findings. | Focused Ruff `E9,F` check on `backend/app/config.py` and `tests/unit/test_config.py` passed; broad lint remains unaddressed. |
| Mypy | Could not parse installed NumPy stubs because current Python typing syntax exceeded the configured target. | Not rerun; unresolved. |
| Docker | Docker CLI is installed, but the Docker Desktop engine pipe is unavailable. | No Compose build/start was run. |
| Migrations | Only the initial revision was present at baseline. | Additive revisions `002_patient_owner` and `003_prediction_input_refs` pass disposable SQLite migration tests in the backend suite. No production/local user database was migrated; PostgreSQL migration execution is unverified. |
| Models | No promoted/verified model in tracked registry; ignored local files are not evidence of training or compatibility. | Inference remains fail-closed. No local checkpoint or private database was used for testing. |

The API tests use isolated in-memory SQLite; migration tests use disposable temporary databases. The local `.env`, local `medfusion.db`, ignored model artifacts, and patient records were not modified.

## 6. Changes in this implementation pass

- Added owner-only patient/case/nested-resource access checks and integration coverage for cross-user denial. Added patient ownership migration with conservative audit-based backfill; ambiguous legacy records remain unowned.
- Added prediction references to the exact image and clinical-record versions, plus a file hash and clinical update timestamp. The case view hides results when current inputs no longer match those references.
- Replaced automatic table creation with an explicit Alembic-head startup check. Added migration URL handling and disposable SQLite migration coverage.
- Added clinical-record update support and corrected case-detail API/type mapping for saved records and predictions.
- Removed clinical templates, random demographic defaults, fake quick-login buttons, unverified model-selection UI, fallback images, fabricated audit events, synthetic explanation baselines, probability-derived localization boxes, and default modality-gating values.
- Protected image/heatmap downloads now use the authenticated API client. Removed storage file paths from frontend image summaries.
- Corrected modality options and show upload quality feedback for the current session. Quality feedback is not persisted across reloads.
- Added ESLint flat config and frontend tests; lint, production build, and all 10 Vitest tests pass. The build retains a large-chunk warning.
- Revised disclaimer, review, prediction, explanation, audit and model UI labels to distinguish stored prototype outputs from validated clinical findings. Corrected explanation client URLs to match the backend routes and verified those paths in OpenAPI.
- Added production configuration validation and focused tests; corrected Docker Compose so the backend uses the database service hostname instead of the host-development `localhost` URL. Compose execution remains unverified because Docker Desktop is unavailable.
- Filtered new audit detail JSON through a technical-metadata allowlist; removed diagnosis text and case numbers from review audit details and case numbers/storage paths from application log messages. Existing database audit rows are unchanged.
- Added a protected, read-only report-preview API and workstation panel. Previews include persisted input/version references and linked review records; stale model output is labeled, stored probabilities remain explicitly unverified, and the response cannot be finalized or delivered.
- Added ReportLab clinical PDF report generation (`GET /api/v1/cases/{case_id}/report-pdf`) with clinician disclaimers, owner scoping, technical audit logging (`report_pdf`), and a frontend "Export PDF" download action in the case report preview panel.
- Added Windows local path normalization (`backend/app/config.py`), fixed Alembic path resolution (`backend/alembic.ini`), and provided a one-click automated setup script (`scripts/setup_local_windows.ps1`).
- Latest integrated backend verification: 179 passed, 14 skipped, 0 failed (193 collected), with 25 warnings; the focused production settings tests cover 16 cases including redacted errors. Frontend lint/build and 6 files/12 tests pass.

These are local working-tree changes and are not committed.

## 7. Prioritized remaining implementation plan

1. **Model integrity:** require compatible checksum-verified metadata and evaluation/preprocessing provenance before promotion; verify image/tabular pipelines; keep inference blocked until evidence exists. Do not load/promote ignored local artifacts without provenance.
2. **Clinical workflow:** complete review finalization/revision semantics, ensure historical and new prediction/input linkage is complete, and add browser-driven workflow tests.
3. **Audit and reports:** expand audit event coverage and define retention; add report artifact persistence, explicit finalization/signature controls, and authorized PDF delivery if required. Avoid immutability claims until technically enforced and independently evaluated.
4. **Clinical preprocessing:** persist/version training-fitted encoders, scalers, and imputers; remove or validate arbitrary `raw_metrics` input.
5. **Configuration and migrations:** production settings have focused unit coverage; exercise application startup under production configuration, validate migrations on PostgreSQL, and document backup/rollback behavior.
6. **Uploads and reliability:** verify proxy-level request limits, storage/database rollback, retention, and concurrent upload/inference behavior.
7. **Frontend:** complete pagination/filtering, verify critical flows in a browser, and split the large JS bundle based on measured route usage.
8. **Deployment and documentation:** add CI and record exact results, remaining privacy limitations, and clinical/regulatory boundaries. Do not claim production readiness or clinical validation.
