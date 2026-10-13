# MedFusion AI — Architecture Overview

> **Implementation note:** This document describes the code layout, not a verified production deployment. There are no provenance-verified active model checkpoints. An owner-scoped JSON report-preview API is present, but no report finalization, PDF, signature, or delivery workflow exists. An administrator/auditor-only audit-events read API is present; it is not tamper-evident. Owner-only checks now scope patient and case resources and nested clinical data. Team/tenant sharing is not implemented; see `SECURITY.md` before handling sensitive records.

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
2. **Business Logic Layer (Services)** — Core domain logic and orchestration. Service-level owner checks scope patient, case, and nested-resource operations. The model has no team/tenant sharing or assignment workflow.
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
- `audit_logs` - Application audit-event rows; a minimal administrator/auditor read API exists, but rows are not immutable or tamper-evident
