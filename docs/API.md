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
- `PATCH /api/v1/cases/{case_id}`
- `POST /api/v1/cases/{case_id}/status`
- `DELETE /api/v1/cases/{case_id}`

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

**Current model availability:** this repository has no trained checkpoint artifacts. Prediction requests that reach inference therefore return HTTP `503 Service Unavailable`; no prediction is persisted. Endpoint presence does not imply a validated model is available.

## Reviews

- `POST /api/v1/cases/{case_id}/reviews`
- `GET /api/v1/cases/{case_id}/reviews`
- `GET /api/v1/predictions/{prediction_id}/reviews`
- `GET /api/v1/reviews/stats`
- `GET /api/v1/reviews`
- `GET /api/v1/reviews/{review_id}`

## Not implemented in the registered API

There is no registered audit-events endpoint, report-generation/delivery endpoint, or administrator user-management endpoint in the inspected router set. Patient/case route authentication is not a substitute for object-level or tenant authorization; see `SECURITY.md` and `IMPLEMENTATION_AUDIT.md`.
