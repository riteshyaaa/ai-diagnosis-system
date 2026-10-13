# Implementation audit

**Audit baseline:** `main` at `9e820afe82b2678791d8581d8969f09c8af5720e`
**Repository:** `riteshyaaa/ai-diagnosis-system`
**Scope:** static repository inspection plus the local verification attempts recorded below. This document does not claim a deployment, database-backed run, or clinical validation.

## A. Initial findings

The repository is a substantial prototype organized as a React/TypeScript frontend, FastAPI/SQLAlchemy backend, PostgreSQL schema and migrations, and a PyTorch-oriented ML subsystem. It includes routers and services for authentication, patients, cases, imaging uploads, clinical records, predictions, explanations, and clinician reviews. It also contains model architectures, synthetic-data generators, training/evaluation code, and Docker configuration.

The presence of code, tests, diagrams, manifests, and documentation is not evidence that the complete product workflows run. Before this pass:

- Public registration accepted a client-selected role and the service persisted it.
- Registry startup could create fresh random-weight networks, label them active, and attach hard-coded evaluation metrics. Its tabular path also created a calibrator from synthetic probability/label pairs.
- The checked-in registry declared three active models and non-empty metrics/checksums, but no checkpoint or calibrator artifact was present in the repository.
- The audit screen displayed hard-coded events and asserted immutable logging and 21 CFR Part 11 compliance. There is no audit-events API in the versioned API routers.
- Upload endpoints read the whole file into memory before the service-level size check.
- Case and patient queries require authentication on many routes but do not consistently enforce record ownership or institutional scope. The repository has no organization/tenant model, so the correct sharing policy cannot be inferred.
- The documentation overstated properties such as immutable audit logging, encryption/anonymization, test coverage, and ready-to-run workflows.
- The prompt refers to a product-presentation PDF. The supplied attachment is the engineering prompt text; the repository tree contains no presentation PDF. Presentation-specific workflows and diagrams therefore could not be inspected.

## B. Changes made in this pass

These edits exist in the local working copy and have **not** been published to GitHub.

- **Backend/auth:** `UserCreate` now rejects extra fields, including `role`; public registration creates only clinician accounts in `backend/app/services/auth_service.py`.
- **Backend/uploads:** `backend/app/utils/uploads.py` caps application-level reads at configured maximum plus one byte. Both case-image upload and direct-inference upload use it.
- **Backend/inference:** missing model artifacts are translated to the existing service-unavailable response. A case is not moved to `PROCESSING` unless inference succeeded.
- **ML/model registry:** startup no longer constructs implicit random baseline models or assigns mock metrics/calibration. New registrations default to `experimental`; default loads require an explicitly promoted version; promotion checks that the artifact exists and its checksum matches.
- **ML metadata:** manifest and model metadata no longer claim active models, checksums, calibrator files, or evaluation metrics that are absent from the repository.
- **Frontend:** public registration types no longer allow a role; `AuditPage.tsx` now reports that no audit-events API is available instead of displaying sample events or a compliance claim.
- **Tests:** registration privilege-escalation cases, no-checkpoint behavior, model-promotion checks, bounded upload reads, and test-only provisioning of privileged roles were added/updated. Inference-dependent explanation/review tests now skip explicitly unless all registered checkpoint files are present; prediction and end-to-end checks expect HTTP 503 and no persisted prediction with the current registry.
- **Documentation:** README, API, architecture, dataset, deployment, ML-pipeline, security, testing, model-card, changelog, and this audit now distinguish source code from verified capabilities.

## C. Verification results

| Check | Result | Evidence / limitation |
|---|---|---|
| Repository access and baseline | **PASS** | GitHub API returned `main` at `9e820afe82b2678791d8581d8969f09c8af5720e`; repository is reachable. |
| Prompt attachment read | **PASS** | Engineering brief was available as text. No PDF was attached or found in the repository. |
| Python test suite (`pytest -q`) | **BLOCKED** | Command could not start: `pytest: command not found`. Runtime also lacks FastAPI, Pydantic, SQLAlchemy, PyTorch, NumPy, and the other project dependencies. |
| Frontend production build (`cd frontend && npm run build`) | **BLOCKED** | Command could not start: `tsc: not found`; `frontend/node_modules` is absent. |
| Test results for this patch | **NOT RUN** | Dependencies are unavailable in this environment; the changed tests have not been executed. |
| Python syntax and registry metadata | **STATIC CHECK PASS** | BOM-aware Python compilation parsed 144 source/test files; 6 JSON files parsed; all 3 registry entries have no active version, fabricated metrics, or unsupported checksum. This does not import dependencies or execute tests. |
| Docker Compose config | **BLOCKED** | The configuration check stopped because repository-root `.env` is absent (`env_file` references it); no temporary environment file was created. |
| Docker daemon/build | **BLOCKED** | `docker info` reported that it could not connect to `/var/run/docker.sock`; no containers were started. |
| CI status | **NOT CONFIGURED** | No repository GitHub Actions workflow was present in the inspected tree. |
| Clinical/model validation | **NOT AVAILABLE** | No real model checkpoints, dataset payloads, evaluation output, or provenance package were found. |

Do not interpret static edits as passed integration tests. Install the repository's pinned dependencies and run the commands in `TESTING.md` before merging.

## D. Capability matrix

Statuses describe what the inspected repository supports, not product promises.

| Capability / requirement | Status | Evidence and limitation |
|---|---|---|
| User login, JWTs, account registration | **IMPLEMENTED_UNVERIFIED** | Routes/services and integration tests exist. Public registration is now clinician-only in this patch; tests could not run. |
| Role-based endpoint checks | **PARTIAL** | Role dependencies exist; object-level and cross-institution access is not consistently enforced. |
| Patient and case CRUD/worklist | **PARTIAL** | API and UI code exist; case lists and resource reads lack a defined tenant/ownership policy. |
| PNG/JPEG/DICOM upload and preprocessing | **IMPLEMENTED_UNVERIFIED** | Processing and validation code exists; API reads are now bounded. End-to-end storage and privacy behavior have not been run here. |
| Image, tabular, and multimodal architectures | **RESEARCH_ONLY** | Model and trainer code exists. Checked-in trained weights and a verified compatible preprocessing bundle are absent. |
| Clinical inference from a verified model | **BLOCKED** | No deployable artifact or evaluation provenance. The patched registry leaves these paths unavailable and API calls return a service-unavailable error rather than random predictions. |
| Calibration and uncertainty claims | **BLOCKED** | The checked-in metrics/calibrator had no verifiable data or artifact provenance; those claims were removed. |
| Grad-CAM / SHAP | **RESEARCH_ONLY** | Implementation code exists, but no real-model output was verified. The tabular explainer can synthesize a random background when none is supplied. |
| Clinician review workflow | **IMPLEMENTED_UNVERIFIED** | Review routes, models, and UI code exist; authorization, persistence, and lifecycle behavior were not executed. |
| Audit-event storage | **PARTIAL** | Audit models/services exist. No versioned audit-events API or immutable/tamper-evident store was found. The frontend now states this limitation. |
| Report generation and controlled delivery | **MISSING** | No report API/service or report generator was found in the inspected source tree. |
| CT/MRI, pathology images, transformer model, emergency triage, chronic disease screening | **NOT_IMPLEMENTED** | Mentioned in the prompt/presentation reference, but no verified supported workflow or model artifact was found. |
| Telemedicine, edge deployment, mobile client | **NOT_IMPLEMENTED** | No implementation was found in the inspected repository. |
| Frontend unit/component tests | **MISSING** | No frontend test files were found despite a Vitest script in `frontend/package.json`. |
| CI checks / deployment verification | **BLOCKED** | No checked-in CI workflow; local build/test commands could not run. |

`IMPLEMENTED_UNVERIFIED` means code exists but this environment did not execute it. `RESEARCH_ONLY` does not mean clinically useful or validated.

## E. Model evidence

The repository contains registry metadata for:

| Registry name | Expected artifact | Artifact found? | Safe for inference? |
|---|---|---:|---|
| `chest_xray_vision` | `chest_xray_vision_v1.0.0.pt` | No | No |
| `tabular_risk_mlp` | `tabular_risk_mlp_v1.0.0.pt` and `calibrator.joblib` | No | No |
| `multimodal_late_fusion` | `multimodal_late_fusion_v1.0.0.pt` | No | No |

No checkpoint checksum can be independently computed, no preprocessing bundle can be matched to a checkpoint, and no evaluation report or dataset provenance is available in the repository. The previously populated manifest metrics are therefore not retained as evidence.

`ml/experiments/` includes synthetic-data training paths. The synthetic generators are useful for software experiments, not evidence of diagnostic performance. No real-data training or clinically relevant validation is claimed.

## F. Security findings

### Fixed in the local working copy

- **Privilege escalation at registration:** removed caller-selected role from the public schema and fixed the persisted role to clinician; added negative API tests.
- **Unbounded application-level upload reads:** bounded image reads for both case uploads and direct inference; added unit tests.
- **Model fallback and false model evidence:** removed random startup models and mock metrics; prevent implicit latest-version loading and block promotion of absent or checksum-mismatched artifacts.
- **Misleading audit UI:** removed hard-coded audit rows and the unsupported compliance label.

### Still open

1. **High — patient/case/image IDOR and cross-user access:** authentication alone does not prove a requester may read or mutate a particular patient/case. The intended collaboration boundary (owner-only, team, or institution-wide) needs the product owner’s decision; do not deploy with sensitive real records until object-level checks and negative tests exist.
2. **High — production configuration:** `DEBUG` defaults to true and secret/database settings include development placeholders. Production startup does not currently reject unsafe values.
3. **High — audit assurance:** audit code is not an immutable or independently verifiable ledger; there is no audit API, retention design, or demonstrated control framework.
4. **Medium — upload defense-in-depth:** bounded reads prevent an unbounded Python allocation, but reverse-proxy/framework request-body limits, concurrency limits, and MIME/magic-byte consistency still need deployment-level validation.
5. **Medium — migrations:** application startup calls `Base.metadata.create_all()` instead of applying Alembic migrations. This is not a reproducible production schema-upgrade strategy.
6. **Medium — session revocation, rate limiting, and retention:** verify actual deployment behavior and implement/validate server-side session invalidation and retention controls as required.
7. **Compliance claims:** no HIPAA, GDPR, 21 CFR Part 11, or other formal compliance assessment was performed. Do not represent this prototype as compliant.

## G. How to run and verify

These are repository commands, **not commands verified in this environment**:

```bash
# From the repository root, after creating a virtual environment and installing
# backend/ML development dependencies from the repository's requirement files:
pytest -q

# Frontend: use the checked-in lockfile for a reproducible install.
cd frontend
npm ci
npm run build
npm run lint
npm run test -- --run
```

For Docker Compose, copy `.env.example` to `.env`, replace development placeholders (especially database password and JWT secret), then use:

```bash
docker compose --env-file .env -f docker/docker-compose.yml config
docker compose --env-file .env -f docker/docker-compose.yml up --build
```

These commands still need to be validated. Compose currently publishes PostgreSQL and the backend on host ports by default; restrict those ports before any shared or production deployment. See `DEPLOYMENT.md` and `TESTING.md` for current limitations.

## H. Remaining work, ranked

1. Decide the organization/team/record access model; enforce it in every patient, case, image, prediction, explanation, review, and report query; add cross-user negative tests.
2. Build a clean dependency environment and run all tests, frontend build/lint, migrations, and Docker checks; fix genuine failures.
3. Obtain the actual presentation PDF and product owner clarification for requirements not represented by the prompt text.
4. Keep inference disabled until real artifacts, training/evaluation provenance, compatible preprocessing, and clinical-use limitations are documented and independently reviewed.
5. Implement real audit-event retrieval/storage semantics and a report-generation/authorization workflow, with tests. Do not restore demo records or compliance labels.
6. Replace startup `create_all()` with an explicit migration strategy and add production configuration validation, health/readiness checks, bounded request handling, and CI.
7. Update architecture/API/dataset/deployment docs against verified behavior and add frontend tests.
8. Perform formal privacy, security, clinical, and regulatory reviews before handling real patient data or making diagnostic claims.

## I. Change summary

The local working-copy edits cover the registration schema/service, inference service and upload routes, model registry/metadata, audit UI, auth/inference/upload tests and test helpers, plus the API, architecture, dataset, deployment, ML-pipeline, security, testing, model-card, changelog, and README documentation. They remain unpublished until a draft PR is approved and created.
