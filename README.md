# MedFusion AI — Multimodal Medical Diagnosis & Clinical Decision Support System

> **⚠️ Medical Disclaimer**: MedFusion AI is an assistive clinical decision support tool designed exclusively for qualified healthcare professionals. It does **not** provide autonomous medical diagnosis and is **never** intended to replace the clinical judgment of a licensed physician.

---

## 🏥 Overview

**MedFusion AI** is an enterprise-grade multimodal artificial intelligence platform that combines medical imaging analysis (chest X-rays) with structured clinical health parameters (tabular laboratory/vitals data) using late-fusion deep learning. The system provides:

- **Multimodal AI Inference** — Combines DenseNet-121 image embeddings with clinical risk predictors for joint diagnostic support.
- **Explainable AI (XAI)** — Grad-CAM visual heatmaps for radiology and SHAP feature importance for clinical values.
- **Calibrated Uncertainty Estimation** — Temperature-scaled prediction probabilities with explicit confidence banding and safety abstention thresholds.
- **Human-in-the-Loop Review Workflow** — Clinicians review, accept, modify, or reject AI findings with mandatory rationale recording.
- **Enterprise Security & Compliance** — JWT authentication, RBAC, encrypted storage, immutable audit logging, and strict data anonymization.

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
git clone https://github.com/your-org/medfusion-ai.git
cd ai_diagnosis

# 2. Configure environment
cp .env.example .env
# Edit .env with your secrets

# 3. Build and run all services
docker compose -f docker/docker-compose.yml up --build -d

# 4. Open in browser:
# Frontend:  http://localhost
# API Docs:  http://localhost:8000/docs
# Health:    http://localhost:8000/health
```

### Option 2: Local Development

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

---

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
│   │   ├── middleware/       # Security Headers, Logging, Rate Limiting
│   │   ├── utils/            # Helpers, PDF Generator
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
├── tests/                    # Test Suite
│   ├── unit/                 # Unit Tests (Backend, Frontend, ML)
│   ├── integration/          # API & Pipeline Integration Tests
│   ├── e2e/                  # End-to-End User Journey Tests
│   └── conftest.py           # Pytest Global Fixtures
│
├── data/                     # Local Dataset Storage (Git-ignored)
├── models/registry/          # Model Artifact Registry (Git-ignored)
├── notebooks/                # Research & Exploration Notebooks
├── scripts/                  # Automation & Utility Scripts
├── .env.example              # Environment Variable Template
├── .gitignore                # Comprehensive Git Ignore Rules
└── Makefile                  # Developer Workflow Shortcuts
```

---

## 🔒 Security & Privacy

- **Data Minimization** — Patient records use cryptographically hashed identifiers.
- **Role-Based Access** — Strict privilege separation across Clinician, Radiologist, Admin, and Auditor roles.
- **Audit Trails** — Every diagnostic inference, clinical review, and sensitive action produces an immutable audit record.
- **Defense in Depth** — Content-Security-Policy headers, rate limiting, magic-byte upload validation, and secure password hashing with bcrypt.

---

## 📄 License

This project is developed for educational, academic, and research purposes.
