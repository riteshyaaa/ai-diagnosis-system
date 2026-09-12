"""
MedFusion AI — FastAPI Application Factory.

Creates and configures the FastAPI application with:
- Lifespan events (database connect/disconnect, model preloading)
- CORS middleware
- Centralized exception handlers for domain exceptions
- Versioned API routers (/api/v1)
- Health check endpoints
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_v1_router
from app.config import get_settings
from app.database import engine
from app.models import Base
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
    Initializes database pools and tables on startup.
    Cleans up resources on shutdown.
    """
    # Startup: Ensure database schema / tables are created
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: Dispose database connection pool
    await engine.dispose()


def create_app() -> FastAPI:
    """Factory creating configured FastAPI instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "MedFusion AI — Clinical Decision Support System API. "
            "Assists healthcare professionals with multimodal AI diagnostic analysis."
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
