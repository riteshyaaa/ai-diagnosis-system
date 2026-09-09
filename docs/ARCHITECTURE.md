# MedFusion AI — Architecture Overview

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
2. **Business Logic Layer (Services)** — Core domain logic, orchestration between repositories and ML inference, business rule enforcement, permission checks.
3. **Data Access Layer (Repositories)** — Direct database interaction via async SQLAlchemy 2.0. No business logic in repositories.
4. **Machine Learning Layer** — Standalone package (`ml/`) with its own dependency isolation. Produces versioned artifacts consumed by the backend inference service.

## Database Schema (High-Level)

- `users` — Authentication, role-based access control (Clinician, Radiologist, Admin, Auditor)
- `patients` — Anonymized demographic data, MRN hash
- `diagnostic_cases` — Top-level case container linking patient, inputs, and results
- `images` — Uploaded medical imaging metadata and storage paths
- `clinical_records` — Structured tabular clinical measurements
- `predictions` — AI inference results, confidence bands, model versions
- `explanations` — Grad-CAM heatmap paths, SHAP values, feature importance
- `clinical_reviews` — Clinician decision (accept/modify/reject), notes, timestamp
- `audit_logs` — Immutable event log for security and compliance
