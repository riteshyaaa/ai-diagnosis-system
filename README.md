# MedFusion AI — Clinical Decision Support Prototype

> **Research prototype only.** This repository is not clinically validated and must not be used to diagnose, triage, or guide treatment. No provenance-verified trained model checkpoint is distributed; inference remains unavailable until a compatible artifact is verified and promoted. It does not establish HIPAA, GDPR, 21 CFR Part 11, or other regulatory compliance.

---

## 🏥 Overview

**MedFusion AI** is a software prototype with a React/TypeScript frontend, FastAPI backend, PostgreSQL data model, and experimental ML code for chest-radiograph, tabular, and multimodal workflows. The repository includes:

- API, persistence, and UI code for authentication, owner-scoped patient/case records, uploads, clinical records, predictions, and reviews; backend API tests cover selected workflows, but no browser-driven end-to-end suite exists.
- An owner-scoped JSON report preview generated from saved case inputs, model output, and reviews. It remains a draft or pending-review preview; PDF generation, signature, and controlled delivery are not implemented.
- Model architectures, synthetic-data experiments, preprocessing, training, and evaluation code; these are research components, not evidence of model performance.
- A fail-closed model registry: absent or unverified weights do not produce predictions.
- A security/audit status overview in [`docs/IMPLEMENTATION_AUDIT.md`](docs/IMPLEMENTATION_AUDIT.md).

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React 18 Frontend                        │
│   (TypeScript, Tailwind CSS, TanStack Query, Recharts)      │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / REST (JWT Auth)
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend                          │
│                                                             │
│   Routers ──► Services ──► Repositories ──► PostgreSQL DB   │
│      │            │                                         │
│      ▼            ▼                                         │
│   Auth / RBAC   Inference Engine ──► Model Registry         │
│                 (PyTorch / XGBoost)  (TorchScript / ONNX)   │
│                       │                                     │
│                       ├──► Grad-CAM (Saliency Map)          │
│                       └──► SHAP (Feature Importance)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/riteshyaaa/ai-diagnosis-system.git
cd ai-diagnosis-system

# 2. Configure environment
cp .env.example .env
# Replace the example database password and JWT secret before use

# 3. Build and run all services
docker compose --env-file .env -f docker/docker-compose.yml up --build -d

# 4. Open in browser:
# Frontend:  http://localhost
# API Docs:  http://localhost:8000/docs
# Health:    http://localhost:8000/health
```

### Option 2: Local Development (Windows PowerShell)

Use a separate development database. Do not point setup or tests at a database containing records you need to keep.

```powershell
# Backend: from the repository root
$env:DATABASE_URL = "sqlite+aiosqlite:///./medfusion-dev.db"
$env:APP_ENV = "development"
$env:DEBUG = "true"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt -r ml/requirements.txt
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

In a second terminal, from `frontend/`:

```powershell
npm ci
npm run dev
```

The API is at `http://localhost:8000`; Vite prints its frontend URL (usually `http://localhost:5173`). Keep the same `DATABASE_URL` in the backend shell for migrations and server startup. Demo personas are seeded only when `DEMO_USERS_ENABLED=true`, `APP_ENV=development`, and `DEBUG=true`; this setting must not be used outside local development.

The backend refuses to start unless Alembic has upgraded the selected database to the current head. Do not run migrations against an existing local database unless you have a backup and intend to upgrade it. Model inference remains unavailable (HTTP 503) until compatible artifacts and provenance are verified and promoted; ignored local files do not change that status.

## 📁 Repository Structure

```
ai_diagnosis/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/v1/           # API Routers (Auth, Patients, Cases, Inference, Reviews)
│   │   ├── models/           # SQLAlchemy ORM Models
│   │   ├── schemas/          # Pydantic Request/Response Schemas
│   │   ├── services/         # Business Logic Layer
│   │   ├── repositories/     # Data Access Layer
│   │   ├── security/         # JWT, Password Hashing, RBAC
│   │   ├── middleware/       # Security headers and request logging
│   │   ├── utils/            # Shared helpers
│   │   ├── config.py         # Application Settings
│   │   ├── exceptions.py     # Custom Exceptions
│   │   └── main.py           # FastAPI Application Factory
│   ├── requirements.txt      # Production Dependencies
│   ├── requirements-dev.txt  # Development & Testing Dependencies
│   └── pyproject.toml        # Ruff, MyPy, Pytest Configuration
│
├── frontend/                 # React 18 + Vite Application
│   ├── src/
│   │   ├── components/       # UI, Common, Layout Components
│   │   ├── pages/            # Route Views (Dashboard, CaseDetail, Review, Audit)
│   │   ├── hooks/            # Custom React Hooks
│   │   ├── services/         # Axios API Client & Endpoint Wrappers
│   │   ├── store/            # Zustand State Stores
│   │   ├── types/            # TypeScript Interfaces & Enums
│   │   ├── utils/            # Formatting & Validation Helpers
│   │   ├── App.tsx           # Root Application & Routing
│   │   └── main.tsx          # Application Entry Point
│   ├── package.json          # Dependencies & Scripts
│   ├── tailwind.config.js    # Medical Theme Design Tokens
│   └── vite.config.ts        # Vite Build Configuration
│
├── ml/                       # Machine Learning Subsystem
│   ├── datasets/             # Data Loaders (NIH ChestX-ray14, UCI Heart Disease)
│   ├── models/               # Model Architectures (Image, Tabular, Fusion)
│   ├── training/             # Training Loops, Callbacks, Loss Functions
│   ├── evaluation/           # Metrics, Calibration, Subgroup Fairness
│   ├── explainability/       # Grad-CAM, SHAP Explanations
│   ├── inference/            # Production Inference Pipeline
│   ├── experiments/          # Training Entry Scripts
│   ├── config.py             # ML Hyperparameters & Config
│   └── requirements.txt      # ML Package Dependencies
│
├── docker/                   # Containerization
│   ├── backend.Dockerfile    # Multi-stage Python 3.11 Image
│   ├── frontend.Dockerfile   # Multi-stage Node + Nginx Image
│   ├── nginx.conf            # Reverse Proxy & Security Headers
│   └── docker-compose.yml    # Multi-container Composition
│
├── docs/                     # Technical Documentation
│   ├── ARCHITECTURE.md       # Detailed System Architecture
│   ├── ML_PIPELINE.md        # ML Training & Inference Guide
│   ├── SECURITY.md           # Security & Compliance Protocols
│   ├── API.md                # REST API Specification
│   ├── DEPLOYMENT.md         # Deployment & Operations Guide
│   ├── DATASET.md            # Dataset Attribution & Schemas
│   └── TESTING.md            # Testing Strategy & Coverage
│
├── tests/                    # Python test suite
│   ├── unit/                 # Backend and ML unit tests
│   ├── integration/          # API & Pipeline Integration Tests
│   ├── e2e/                  # End-to-End User Journey Tests
│   └── conftest.py           # Pytest Global Fixtures
│
├── data/                     # Local Dataset Storage (Git-ignored)
├── models/registry/          # Registry metadata; no trained weights are included
├── notebooks/                # Research & Exploration Notebooks
├── scripts/                  # Automation & Utility Scripts
├── .env.example              # Environment Variable Template
├── .gitignore                # Comprehensive Git Ignore Rules
└── Makefile                  # Developer Workflow Shortcuts
```

---

## Security & privacy status

- Password hashing, JWT authentication, and endpoint role dependencies are present; public registration creates clinician accounts only.
- Patient and case access is owner-scoped in the current implementation; there is no organization/team sharing model. Legacy patients without a uniquely evidenced owner stay inaccessible. Do not use real patient data because the system has no clinical validation and other deployment/security controls remain incomplete.
- The audit page reads a minimal administrator/auditor-only API. Events omit free-form details and network metadata; the database rows are not tamper-evident or a compliance certification.
- Upload reads are bounded in the API, but request-body limits and other deployment-level protections still need verification.
- See [`docs/SECURITY.md`](docs/SECURITY.md) for controls and remaining risks. No compliance certification is claimed.

---

## 📄 License

This project is developed for educational, academic, and research purposes.
