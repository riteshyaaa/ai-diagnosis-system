# ============================================================
# MedFusion AI — Makefile
# Common developer workflows and automation targets
# ============================================================

.PHONY: help install dev backend-dev frontend-dev test test-backend test-frontend lint format clean docker-up docker-down

help:
	@echo "MedFusion AI — Available Commands"
	@echo "=================================="
	@echo "  install        Install all dependencies (backend + frontend + ml)"
	@echo "  dev            Run both backend and frontend development servers"
	@echo "  backend-dev    Run FastAPI development server"
	@echo "  frontend-dev   Run React/Vite development server"
	@echo "  test           Run all tests"
	@echo "  test-backend   Run backend pytest suite"
	@echo "  test-frontend  Run frontend vitest suite"
	@echo "  lint           Run code linters (ruff, mypy, eslint)"
	@echo "  format         Run code formatters"
	@echo "  docker-up      Start all services with Docker Compose"
	@echo "  docker-down    Stop all Docker Compose services"
	@echo "  clean          Remove temporary files and build artifacts"

install:
	cd backend && pip install -r requirements-dev.txt
	cd frontend && npm install
	cd ml && pip install -r requirements.txt

backend-dev:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev

test-backend:
	pytest tests/unit/ -v --cov=backend/app

test-frontend:
	cd frontend && npm run test

test: test-backend test-frontend

lint:
	cd backend && ruff check .
	cd backend && mypy app/
	cd frontend && npm run lint

format:
	cd backend && ruff format .

docker-up:
	docker compose -f docker/docker-compose.yml up --build -d

docker-down:
	docker compose -f docker/docker-compose.yml down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist frontend/node_modules/.vite
