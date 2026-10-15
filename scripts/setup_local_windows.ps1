# ==============================================================================
# MedFusion AI — Local Windows Setup Script (PowerShell)
# ==============================================================================
# Automated local development setup for Windows.
# Run from repository root: .\scripts\setup_local_windows.ps1
# ==============================================================================

param(
    [string]$DatabaseUrl = "sqlite+aiosqlite:///./medfusion-dev.db"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\backend\alembic.ini")) {
    throw "Run this script from the repository root."
}

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCommand) {
    throw "Python 3.11 or newer is required. Install Python and ensure 'python' is on PATH."
}
$PythonVersion = & $PythonCommand.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$PythonVersion -lt [version]"3.11") {
    throw "Python 3.11 or newer is required; found Python $PythonVersion."
}

$NodeCommand = Get-Command node -ErrorAction SilentlyContinue
if (-not $NodeCommand) {
    throw "Node.js 20 or newer is required. Install Node.js and ensure 'node' is on PATH."
}
$NodeVersion = (& $NodeCommand.Source --version).Trim().TrimStart([char]"v")
if ([version]$NodeVersion -lt [version]"20.0") {
    throw "Node.js 20 or newer is required; found Node.js $NodeVersion."
}

# Use a separate local development database for this PowerShell session.
# This does not write to or replace the repository's .env file.
$env:DATABASE_URL = $DatabaseUrl
$env:APP_ENV = "development"
$env:DEBUG = "true"
$env:DEMO_USERS_ENABLED = "false"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " MedFusion AI - Local Development Setup (Windows)           " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Using the configured development database (connection string is not echoed)." -ForegroundColor DarkGray

# 1. Verify / Create Python Virtual Environment
$VenvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "`n[1/5] Creating Python virtual environment in .venv..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "`n[1/5] Python virtual environment already exists in .venv." -ForegroundColor Green
}
$VenvPythonVersion = & $VenvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$VenvPythonVersion -lt [version]"3.11") {
    throw "The existing .venv uses Python $VenvPythonVersion; recreate it with Python 3.11 or newer."
}

# 2. Install Python Dependencies
Write-Host "`n[2/5] Installing backend and ML dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r backend/requirements-dev.txt -r ml/requirements.txt

# 3. Initialize local directories and apply database migrations
Write-Host "`n[3/5] Initializing local storage directories and database..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path ".\uploads\images\raw" | Out-Null
New-Item -ItemType Directory -Force -Path ".\uploads\images\processed" | Out-Null
New-Item -ItemType Directory -Force -Path ".\uploads\images\thumbnails" | Out-Null
New-Item -ItemType Directory -Force -Path ".\uploads\heatmaps" | Out-Null

& $VenvPython scripts/init_db.py

# 4. Install Frontend Dependencies
Write-Host "`n[4/5] Installing frontend dependencies..." -ForegroundColor Yellow
Push-Location frontend
try {
    npm ci
} finally {
    Pop-Location
}

# 5. Summary & Instructions
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " Setup complete! Services are ready for local execution.   " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "`nTo start the Backend API server (Terminal 1):" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs"
Write-Host "  Health:   http://localhost:8000/health"

Write-Host "`nTo start the Frontend Vite server (Terminal 2):" -ForegroundColor Cyan
Write-Host "  cd frontend" -ForegroundColor White
Write-Host "  npm run dev" -ForegroundColor White
Write-Host "  Application UI: http://localhost:3000"
Write-Host "`nThis shell uses the development DATABASE_URL above. In another shell, set the same value before starting the backend." -ForegroundColor DarkGray

Write-Host "`nTo run automated test suites:" -ForegroundColor Cyan
Write-Host "  Backend Tests:  .\.venv\Scripts\python.exe -m pytest -q" -ForegroundColor White
Write-Host "  Frontend Tests: cd frontend; npm test -- --run" -ForegroundColor White
