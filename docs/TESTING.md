# MedFusion AI — Testing Strategy

## Test Philosophy

MedFusion AI maintains high test coverage across all layers to ensure clinical reliability, security, and reproducibility.

## Test Structure

```
tests/
├── unit/
│   ├── backend/          # FastAPI routers, services, repositories
│   ├── ml/               # Data loaders, model forward pass, loss functions
│   └── frontend/         # Component rendering, custom hooks, utilities
├── integration/
│   ├── api/              # Full HTTP request-response flows with test DB
│   └── ml_pipeline/      # End-to-end training and inference pipeline
└── e2e/                  # Critical user journeys (login → upload → infer → review)
```

## Running Tests

### Backend Tests
```bash
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing
```

### Frontend Tests
```bash
cd frontend
npm run test
```

### ML Tests
```bash
pytest tests/unit/ml/ -v
```
