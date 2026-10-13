# Security status and limitations

## Scope

This file records controls visible in the repository and gaps found by static inspection. It is not a security certification, threat-model sign-off, privacy assessment, or compliance attestation. Do not use this prototype with real patient data.

## Controls present in code

- Password hashing, JWT-based authentication, account lockout logic, and role-check dependencies exist.
- Pydantic schemas validate API input.
- Image-processing code validates formats and applies a configured file-size limit after receiving bytes.
- Case-image and direct-inference API routes now use bounded reads (configured maximum plus one byte) before passing content to image processing.
- Stored image paths are derived from server-side identifiers and configured storage directories.
- Patient, case, image, clinical record, prediction, explanation, and review operations are owner-scoped in service code; cross-user negative API tests cover those boundaries. Legacy patient ownership is backfilled only where a unique create-event actor exists.
- New audit-event details pass through a repository allowlist that keeps only bounded technical metadata and drops clinical/free text, identifiers, filenames, file hashes, and paths. A repository test covers diagnosis/note redaction.
- Missing model artifacts no longer trigger random model construction; unpromoted/missing models remain unavailable.
- Security headers, CORS configuration, and a Docker reverse proxy are present in the repository.

The existence of a control in source does not demonstrate that it is enabled or effective in a deployed environment.

## Important limitations

### Authorization and tenant boundaries

Owner-only record checks are implemented for patient, case, image, clinical-record, prediction, explanation, and review operations and have cross-user API tests. There is no institution/team membership model, sharing workflow, or administrative assignment path. Patients with ambiguous legacy ownership remain inaccessible. This does not make the prototype appropriate for sensitive real records.

### Registration and privileged roles

Public registration now rejects a supplied role and always creates a clinician account. Privileged accounts must be provisioned through a separate, protected operational process; public self-service must not be used to create administrators or auditors.

### Upload handling

The Python read is bounded, but request size limits should also be enforced at the reverse proxy/ASGI boundary. Validate real DICOM/PNG/JPEG content against declared MIME type, limit concurrent processing, and test malformed/oversized files in the deployment environment.

### Secrets and production configuration

`.env.example` contains development placeholders. Replace them locally; never commit real values. When `APP_ENV=production`, application configuration rejects `DEBUG=true`, demo users, a short or placeholder signing key, non-PostgreSQL/loopback database URLs, weak/default database credentials, and non-HTTPS CORS origins. These checks are covered by unit tests, but do not establish that deployment secrets are generated, stored, rotated, or protected correctly. Key rotation, least-privilege service accounts, HTTPS termination, and safe port exposure remain deployment tasks.

### Audit and compliance

A read-only audit-events API is restricted to administrator/auditor roles and omits free-form details, IP addresses, and user-agent strings from responses. New audit details are filtered before persistence, but previously stored rows are not rewritten. Some event types may not be recorded, and no retention, immutability, or tamper-evidence guarantee exists. No HIPAA, GDPR, 21 CFR Part 11, or other compliance status is asserted or established by this repository.

### Model/data safety

There are no trained model checkpoints or evaluation provenance in the checked-in repository. Model metadata has been marked experimental and inference fails closed until a verified artifact is registered and promoted. Synthetic training data is not suitable evidence for clinical use.

### Database and retention

Startup now verifies that the selected database is at the current Alembic head and fails otherwise; it does not create tables automatically. Additive migration tests use disposable SQLite databases, but PostgreSQL deployment execution is not verified. Retention, deletion, backups, recovery, and access auditing still require explicit operational policies and tests.

## Before any shared or production deployment

1. Preserve the owner-only access boundary; implement and test any future team/organization sharing before enabling it.
2. Require safe production secrets and settings at startup.
3. Restrict PostgreSQL and backend host ports; use TLS and proxy-level body/time/concurrency limits.
4. Apply reviewed Alembic migrations to a backup-protected target and document rollback/recovery.
5. Review audit coverage and define retention/tamper-evidence controls if required; undergo formal compliance review before making a compliance claim.
6. Keep model inference disabled until artifact, preprocessing, training-data, evaluation, and review evidence are independently verified.

See `IMPLEMENTATION_AUDIT.md` for findings and `MODEL_CARD.md` for model availability.
