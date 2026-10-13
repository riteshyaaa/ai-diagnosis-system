# API reference (source-level inventory)

The routes below are registered in `backend/app/api/v1/`. This is a source inventory, not a claim that they were exercised successfully. When `DEBUG=true`, FastAPI serves OpenAPI at `/openapi.json` and Swagger UI at `/docs`; production settings hide those pages.

## Base URLs

- Local API root: `http://localhost:8000`
- Versioned API prefix: `/api/v1`
- Health route: `GET /health` (outside the versioned prefix)

The health route currently returns a static application status/version/environment response. It does not verify database, migration, or model readiness.

## Authentication

Routes:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/register` — public self-registration; creates a clinician account only
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/change-password`
- `POST /api/v1/auth/logout`

Protected routes use an `Authorization: Bearer <access_token>` header. Registration does not provision privileged roles. Use a protected operational process for privileged accounts.

## Patients and cases

- `POST /api/v1/patients`
- `GET /api/v1/patients`
- `GET /api/v1/patients/{patient_id}`
- `GET /api/v1/patients/search/mrn`
- `PATCH /api/v1/patients/{patient_id}`
- `POST /api/v1/cases`
- `GET /api/v1/cases`
- `GET /api/v1/cases/{case_id}`
- `GET /api/v1/cases/{case_id}/details`
- `GET /api/v1/cases/{case_id}/report-preview` â€” owner-scoped JSON preview generated from persisted case records
- `PATCH /api/v1/cases/{case_id}`
- `POST /api/v1/cases/{case_id}/status`
- `DELETE /api/v1/cases/{case_id}`

The report preview omits MRN hashes, free-text notes, and arbitrary `raw_metrics`; it includes exact image/clinical input references and marks stored model output as current or stale against those inputs. It labels stored probabilities as unverified and reports only `DRAFT` or `PENDING_REVIEW`. It is not persisted and does not create a finalized PDF, signature, or controlled-delivery artifact.

## Inputs and images

- `POST /api/v1/cases/{case_id}/clinical-records`
- `GET /api/v1/cases/{case_id}/clinical-records`
- `GET /api/v1/clinical-records/{record_id}`
- `PATCH /api/v1/clinical-records/{record_id}`
- `DELETE /api/v1/clinical-records/{record_id}`
- `POST /api/v1/cases/{case_id}/images`
- `GET /api/v1/cases/{case_id}/images`
- `GET /api/v1/images/{image_id}`
- `GET /api/v1/images/{image_id}/file`
- `DELETE /api/v1/images/{image_id}`

The image and direct-inference upload routes use bounded application-level reads based on `MAX_UPLOAD_SIZE_MB`. Configure proxy/body limits separately.

## Predictions and explanations

- `POST /api/v1/cases/{case_id}/predict`
- `GET /api/v1/cases/{case_id}/predictions`
- `GET /api/v1/cases/{case_id}/predictions/latest`
- `GET /api/v1/predictions/{prediction_id}`
- `GET /api/v1/predictions`
- `POST /api/v1/predictions/direct`
- `POST /api/v1/predictions/direct-upload`
- `GET /api/v1/predictions/{prediction_id}/explanation`
- `GET /api/v1/predictions/{prediction_id}/heatmap`
- `GET /api/v1/predictions/{prediction_id}/features`
- `GET /api/v1/cases/{case_id}/explanations`
- `POST /api/v1/predictions/{prediction_id}/explain-pathology`

**Current model availability:** the tracked registry has no active, provenance-verified checkpoint. Prediction requests therefore return HTTP `503 Service Unavailable`; no prediction is persisted. Endpoint presence does not imply a validated model is available.

## Reviews

- `POST /api/v1/cases/{case_id}/reviews`
- `GET /api/v1/cases/{case_id}/reviews`
- `GET /api/v1/predictions/{prediction_id}/reviews`
- `GET /api/v1/reviews/stats`
- `GET /api/v1/reviews`
- `GET /api/v1/reviews/{review_id}`

## Audit events

- `GET /api/v1/audit-events` (administrator/auditor roles only)
- Optional filters: `actor_id`, `action`, `resource_type`, `start_time`, and `end_time`
- Pagination: `skip` (default `0`) and `limit` (default `25`, maximum `100`)
- The response includes event ID, actor UUID, action, resource type/ID, and timestamp. It omits free-form `details`, IP address, and user-agent fields.

This is a read-only view over ordinary database rows. It is not immutable or tamper-evident. Some event types may not be recorded by the current application.

## Not implemented in the registered API

There is no finalized report/PDF delivery or administrator user-management endpoint. Patient/case route authentication is not a substitute for object-level or tenant authorization; see `SECURITY.md` and `IMPLEMENTATION_AUDIT.md`.
