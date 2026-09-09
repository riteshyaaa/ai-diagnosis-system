# MedFusion AI — Deployment Guide

## Prerequisites

- Docker Engine 24.0+ and Docker Compose v2.20+
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)
- PostgreSQL 16+ (if running without Docker)

## Quick Start (Docker Compose)

1. Clone repository:
   ```bash
   git clone <repo-url>
   cd ai_diagnosis
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env and set secure SECRET_KEY and DB_PASSWORD
   ```

3. Build and launch:
   ```bash
   docker compose -f docker/docker-compose.yml up --build -d
   ```

4. Verify deployment:
   - Frontend: `http://localhost`
   - Backend API Docs: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/health`

## Local Development (Without Docker)

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### ML Subsystem
```bash
cd ml
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
