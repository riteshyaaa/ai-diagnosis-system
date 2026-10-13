"""
MedFusion AI — FastAPI Application Factory.

Creates and configures the FastAPI application with:
- Lifespan events (database schema validation and resource cleanup)
- CORS middleware
- Centralized exception handlers for domain exceptions
- Versioned API routers (/api/v1)
- Health check endpoints
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import api_v1_router
from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.services.demo_user_service import seed_demo_users
from app.exceptions import (
    AccountLockedError,
    AuthenticationError,
    AuthorizationError,
    DuplicateError,
    FileValidationError,
    InferenceError,
    ModelNotFoundError,
    NotFoundError,
    PreprocessingError,
    ValidationError,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Validates the migrated database schema before serving requests.
    Cleans up resources on shutdown.
    """
    # Application startup verifies the schema but never creates or alters tables.
    # Apply reviewed Alembic migrations explicitly before starting the service.
    migration_directory = Path(__file__).resolve().parents[1] / "alembic"
    expected_revisions = set(ScriptDirectory(str(migration_directory)).get_heads())
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            applied_revisions = set(result.scalars().all())
    except SQLAlchemyError as exc:
        raise RuntimeError(
            "Database migrations are missing or unreadable. From the backend directory, "
            "run `alembic upgrade head` before starting MedFusion AI."
        ) from exc

    if applied_revisions != expected_revisions:
        raise RuntimeError(
            "Database schema revision does not match this application. From the backend "
            "directory, run `alembic upgrade head` before starting MedFusion AI."
        )
    if settings.demo_users_enabled and settings.debug and settings.app_env == "development":
        async with AsyncSessionLocal() as session:
            await seed_demo_users(session)
            await session.commit()
    yield
    # Shutdown: Dispose database connection pool
    await engine.dispose()


def create_app() -> FastAPI:
    """Factory creating configured FastAPI instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "MedFusion AI engineering prototype API. Inference remains unavailable until a "
            "compatible model artifact is verified and promoted. Stored outputs are not "
            "clinically validated and do not replace clinician judgment."
        ),
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Centralized Exception Handlers ---
    @app.exception_handler(AuthenticationError)
    async def auth_exception_handler(request: Request, exc: AuthenticationError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "AuthenticationError", "detail": exc.message},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(AccountLockedError)
    async def account_locked_exception_handler(request: Request, exc: AccountLockedError):
        return JSONResponse(
            status_code=status.HTTP_423_LOCKED,
            content={"error": "AccountLockedError", "detail": exc.message},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_exception_handler(request: Request, exc: AuthorizationError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "AuthorizationError", "detail": exc.message},
        )

    @app.exception_handler(NotFoundError)
    async def not_found_exception_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "NotFoundError", "detail": exc.message},
        )

    @app.exception_handler(DuplicateError)
    async def duplicate_exception_handler(request: Request, exc: DuplicateError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "DuplicateError", "detail": exc.message},
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "ValidationError", "detail": exc.message},
        )

    @app.exception_handler(FileValidationError)
    async def file_validation_exception_handler(request: Request, exc: FileValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "FileValidationError", "detail": exc.message},
        )

    @app.exception_handler(PreprocessingError)
    async def preprocessing_exception_handler(request: Request, exc: PreprocessingError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "PreprocessingError", "detail": exc.message},
        )

    @app.exception_handler(ModelNotFoundError)
    async def model_not_found_exception_handler(request: Request, exc: ModelNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "ModelNotFoundError", "detail": exc.message},
        )

    @app.exception_handler(InferenceError)
    async def inference_exception_handler(request: Request, exc: InferenceError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "InferenceError", "detail": exc.message},
        )

    # --- Mount Routers ---
    app.include_router(api_v1_router)

    # --- System Health Endpoint ---
    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        """System health and operational status check."""
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.app_env,
        }

    return app


app = create_app()
