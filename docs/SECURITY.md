# Security status and limitations

## Scope

This file records controls visible in the repository and gaps found by static inspection. It is not a security certification, threat-model sign-off, privacy assessment, or compliance attestation. Do not use this prototype with real patient data.

## Controls present in code

- Password hashing, JWT-based authentication, account lockout logic, and role-check dependencies exist.
- Pydantic schemas validate API input.
- Image-processing code validates formats and applies a configured file-size limit after receiving bytes.
- Case-image and direct-inference API routes now use bounded reads (configured maximum plus one byte) before passing content to image processing.
- Stored image paths are derived from server-side identifiers and configured storage directories.
- Missing model artifacts no longer trigger random model construction; unpromoted/missing models remain unavailable.
- Security headers, CORS configuration, and a Docker reverse proxy are present in the repository.

The existence of a control in source does not demonstrate that it is enabled or effective in a deployed environment.

## Important limitations

### Authorization and tenant boundaries

Authentication and role dependencies do not consistently enforce record-level authorization. Case, patient, image, prediction, and related lookups must be reviewed for cross-user access. The codebase does not define institution/team membership, so the product owner must decide whether access is owner-only, team-based, or institution-wide before authorization can be implemented consistently. Until then, do not expose sensitive real records.

### Registration and privileged roles

Public registration now rejects a supplied role and always creates a clinician account. Privileged accounts must be provisioned through a separate, protected operational process; public self-service must not be used to create administrators or auditors.

### Upload handling

The Python read is bounded, but request size limits should also be enforced at the reverse proxy/ASGI boundary. Validate real DICOM/PNG/JPEG content against declared MIME type, limit concurrent processing, and test malformed/oversized files in the deployment environment.

### Secrets and production configuration

`.env.example` contains development placeholders. Replace them locally; never commit real values. Application configuration currently defaults `DEBUG` to true and does not reject placeholder JWT/database credentials when `APP_ENV=production`. Production configuration validation, key rotation, least-privilege service accounts, HTTPS termination, and safe port exposure remain deployment tasks.

### Audit and compliance

Audit models/services exist, but no audit-events API or demonstrated tamper-evident/immutable storage was found. The frontend explicitly reports that audit history is unavailable. No HIPAA, GDPR, 21 CFR Part 11, or other compliance status is asserted or established by this repository.

### Model/data safety

There are no trained model checkpoints or evaluation provenance in the checked-in repository. Model metadata has been marked experimental and inference fails closed until a verified artifact is registered and promoted. Synthetic training data is not suitable evidence for clinical use.

### Database and retention

The application startup path calls SQLAlchemy `create_all()` rather than applying Alembic migrations. Retention, deletion, backups, recovery, and access auditing require explicit operational policies and tests.

## Before any shared or production deployment

1. Decide and implement object-level access boundaries, then test access across users and roles.
2. Require safe production secrets and settings at startup.
3. Restrict PostgreSQL and backend host ports; use TLS and proxy-level body/time/concurrency limits.
4. Replace implicit startup schema creation with controlled migrations and documented rollback/recovery.
5. Implement an actual audit event API and retention/tamper-evidence design if required; undergo formal compliance review before making a compliance claim.
6. Keep model inference disabled until artifact, preprocessing, training-data, evaluation, and review evidence are independently verified.

See `IMPLEMENTATION_AUDIT.md` for findings and `MODEL_CARD.md` for model availability.
