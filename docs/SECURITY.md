# MedFusion AI — Security & Compliance

## Security Architecture

MedFusion AI implements defense-in-depth principles suitable for handling sensitive health data.

### Authentication & Authorization

- **JWT Tokens** — Short-lived access tokens (15–30 min) and long-lived refresh tokens (7 days) with rotation.
- **Password Hashing** — bcrypt with a minimum work factor of 12 rounds.
- **Role-Based Access Control (RBAC)**:
  - `Admin` — User management, system configuration, audit review.
  - `Clinician` — Case creation, clinical data entry, AI inference, review submission.
  - `Radiologist` — Image upload, image-specific AI inference, imaging review.
  - `Auditor` — Read-only access to audit logs, compliance reports, system metrics.
- **Account Lockout** — 5 consecutive failed login attempts locks the account for 15 minutes.

### Data Protection

- **Anonymization** — Patient identifiers are hashed; no raw PII in database or logs.
- **Input Validation** — Strict schema validation on all inputs (Pydantic + pandera).
- **File Upload Security** — Magic-byte verification (not just file extension), file size limits (20MB max), path traversal prevention, storage outside the web root.
- **Transport Security** — HTTPS-ready configuration with secure headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options).

### Audit Logging

All security-sensitive and clinical actions generate immutable audit log entries:
- User logins, logouts, and failed attempts
- Patient and case record creation / modification
- AI inference runs (recording model version, input hashes, prediction ID)
- Clinician review decisions (accept / modify / reject with rationale)
- Configuration and user permission changes
