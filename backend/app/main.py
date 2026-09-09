"""
MedFusion AI — FastAPI Application Entry Point.

This module creates and configures the FastAPI application.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle: startup and shutdown events."""
    settings = get_settings()
    logger.info(
        "Starting %s (env=%s, debug=%s)",
        settings.app_name,
        settings.app_env,
        settings.debug,
    )
    # Startup: initialize resources (DB pool, model loading, etc.)
    # These will be implemented in subsequent phases.
    yield
    # Shutdown: clean up resources
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "AI-Powered Multimodal Clinical Decision Support System. "
            "This system assists healthcare professionals and does NOT "
            "provide autonomous medical diagnosis."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Health Check ---
    @app.get("/health", tags=["system"])
    async def health_check() -> dict:
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": "0.1.0",
        }

    # --- API Routers ---
    # Routers will be registered in Phase 2+.
    # Example:
    #   from app.api.router import api_router
    #   app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
