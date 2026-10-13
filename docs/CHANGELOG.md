# Changelog

## Unreleased — safety and evidence integrity

- Prevented public self-registration from assigning roles; new accounts are clinician-only.
- Bounded application-level reads on both case-image and direct-inference uploads.
- Removed automatic random-weight model creation and synthetic placeholder evaluation/calibration from registry initialization.
- Made unpromoted model versions unavailable to default inference; promotion now checks artifact presence and checksum.
- Cleared unsupported active-model, checksum, calibrator, and performance claims from the checked-in model metadata.
- Return service-unavailable for missing model artifacts and avoid changing a case to `PROCESSING` before inference succeeds.
- Removed fabricated audit rows and the unsupported 21 CFR Part 11 label from the audit page.
- Updated tests to assert fail-closed inference rather than random-weight clinical-looking output; added upload and role-escalation regression tests.
- Added repository audit and model card; current executable check results are recorded in `docs/TESTING.md`.

- Added owner-only authorization across patients, cases, images, clinical records, predictions, explanations, and reviews, with cross-user API regressions.
- Added conservative patient-owner backfill and prediction-to-input reference migrations.
- Replaced automatic table creation with a current-Alembic-head startup check.
- Removed unsupported UI defaults and synthetic explanation artifacts; updated clinical-scope messaging.
- Added frontend lint configuration and focused Vitest coverage.
- Current verification: backend 177 passed/14 skipped (191 collected, 30 warnings); frontend lint/build/12 tests passed. Warnings came from existing PyTorch hook deprecation and SHAP/scikit-learn convergence behavior.
- Corrected frontend explanation-client routes to match the backend API and made unavailable attribution behavior explicit.
- Added a read-only administrator/auditor audit-events API with pagination and filters; responses omit free-form details and network metadata. Wired the audit page to this API. The audit store remains mutable and event coverage is incomplete.
- Added production settings checks for debug/demo mode, signing keys, database engine/host/credentials, and HTTPS CORS origins. Validation errors are redacted and regression-tested not to echo database credentials.
- Updated Compose networking so backend settings derive a URL using the `db` service hostname and configured `POSTGRES_*` values.
- Filtered newly written audit detail JSON to bounded technical metadata; removed diagnosis text, case numbers, and storage paths from review audit details and application log messages. Existing audit rows were not rewritten.
- Added owner-scoped `GET /cases/{case_id}/report-preview` and a workstation preview panel. It reads persisted records, flags stale inputs, omits MRN hashes/free-text notes, and cannot be finalized or delivered as a signed report.
