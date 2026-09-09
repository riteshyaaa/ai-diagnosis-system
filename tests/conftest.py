"""
MedFusion AI — Pytest Configuration and Global Fixtures.
"""

import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport

from app.main import create_app
from app.config import Settings, get_settings


def get_test_settings() -> Settings:
    """Override settings for test environment."""
    return Settings(
        app_env="testing",
        debug=True,
        jwt_secret_key="test-secret-key-for-testing-only-do-not-use-in-production-min-32-chars",
        jwt_access_token_expire_minutes=5,
        jwt_refresh_token_expire_days=1,
        db_host="localhost",
        db_port=5432,
        db_user="test_user",
        db_password="test_password",
        db_name="medfusion_test",
    )


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provide test settings fixture."""
    return get_test_settings()


@pytest.fixture
async def client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async test client for FastAPI application."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
