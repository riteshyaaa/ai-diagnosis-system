# MedFusion AI — API Specification

## Base URL

- Development: `http://localhost:8000/api/v1`
- Production: `https://<domain>/api/v1`

## Authentication

All endpoints except `/auth/login`, `/auth/refresh`, and `/health` require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

## Core Endpoints

### System
- `GET /health` — Health check (database, model service status)

### Authentication (`/auth`)
- `POST /auth/login` — Authenticate and receive token pair
- `POST /auth/refresh` — Exchange refresh token for new access token
- `POST /auth/logout` — Invalidate current session
- `GET /auth/me` — Current authenticated user profile

### Patients (`/patients`)
- `POST /patients` — Register new patient (anonymized)
- `GET /patients` — List patients (paginated, searchable)
- `GET /patients/{id}` — Patient detail and history

### Cases (`/cases`)
- `POST /cases` — Create a new diagnostic case
- `GET /cases` — List cases with filtering (status, modality, date)
- `GET /cases/{id}` — Full case detail including inputs, predictions, reviews
- `POST /cases/{id}/images` — Upload medical image
- `POST /cases/{id}/clinical-data` — Submit tabular clinical parameters

### Inference (`/inference`)
- `POST /inference/image` — Run image-only model
- `POST /inference/tabular` — Run tabular-only model
- `POST /inference/multimodal` — Run multimodal fusion model
- `GET /inference/{id}/explanation` — Retrieve Grad-CAM heatmap / SHAP values

### Reviews (`/reviews`)
- `POST /reviews` — Submit clinician decision (accept / modify / reject)
- `GET /reviews/case/{case_id}` — Review history for a case

### Audit & Admin (`/admin`)
- `GET /admin/audit-logs` — Query audit trail (Auditor/Admin only)
- `GET /admin/users` — Manage users (Admin only)
