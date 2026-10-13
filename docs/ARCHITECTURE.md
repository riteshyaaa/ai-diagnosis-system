# MedFusion AI — Architecture Overview

> **Implementation note:** This document describes the code layout, not a verified production deployment. There are no model checkpoints, audit-events API, or report API in the checked-in source. Record-level and tenant authorization is incomplete; see `SECURITY.md` before handling sensitive records.

## System Architecture

MedFusion AI is structured as a **modular monolith** with clear separation of concerns across presentation, business logic, persistence, and machine learning components.

```
┌─────────────────────────────────────────────────────────────┐
│                    React 18 Frontend                        │
│  (TypeScript, Tailwind CSS, TanStack Query, Zustand, Recharts)│
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / REST (JWT Auth)
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend                          │
│                                                             │
│   Routers ──► Services ──► Repositories ──► PostgreSQL DB   │
│      │            │                                         │
│      ▼            ▼                                         │
│   Auth / RBAC   Inference Engine ──► Model Registry         │
│                 (Torch / XGBoost)    (ONNX / TorchScript)   │
│                       │                                     │
│                       ├──► Grad-CAM (Image Saliency)        │
│                       └──► SHAP (Tabular Importance)        │
└─────────────────────────────────────────────────────────────┘
```

## Layered Design Pattern

1. **Presentation Layer (Routers)** — Request validation (Pydantic), response serialization, HTTP status mapping, dependency injection (DB sessions, current user).
2. **Business Logic Layer (Services)** — Core domain logic and orchestration. Route role checks exist, but object-level permission checks are not consistently enforced.
3. **Data Access Layer (Repositories)** — Direct database interaction via async SQLAlchemy 2.0. No business logic in repositories.
4. **Machine Learning Layer** — Python package (`ml/`) with separate requirement files. Model architectures, experiments, and inference code exist, but no verified checkpoint is checked in and inference remains unavailable.

## Database Schema (High-Level)

- `users` — Authentication, role-based access control (Clinician, Radiologist, Admin, Auditor)
- `patients` — Anonymized demographic data, MRN hash
- `diagnostic_cases` — Top-level case container linking patient, inputs, and results
- `images` — Uploaded medical imaging metadata and storage paths
- `clinical_records` — Structured tabular clinical measurements
- `predictions` — AI inference results, confidence bands, model versions
- `explanations` — Grad-CAM heatmap paths, SHAP values, feature importance
- `clinical_reviews` — Clinician decision (accept/modify/reject), notes, timestamp
- `audit_logs` — Audit event records; no immutable/tamper-evident guarantee or read API is demonstrated
