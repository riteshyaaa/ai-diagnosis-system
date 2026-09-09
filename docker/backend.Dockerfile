# ============================================================
# MedFusion AI — Backend Dockerfile
# Multi-stage build for production FastAPI server
# ============================================================

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# --- Dependency stage ---
FROM base AS dependencies

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Production stage ---
FROM dependencies AS production

# Create non-root user for security
RUN groupadd --gid 1000 medfusion && \
    useradd --uid 1000 --gid medfusion --create-home medfusion

COPY backend/app ./app

# Create directories for uploads and logs
RUN mkdir -p /app/uploads /app/logs && \
    chown -R medfusion:medfusion /app

USER medfusion

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
