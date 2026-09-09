"""
MedFusion AI — Pytest Configuration and Global Fixtures.
"""

from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.database import get_db
from app.main import create_app
from app.models.base import Base

# Test in-memory SQLite async engine
TEST_SQLITE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_SQLITE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_test_settings() -> Settings:
    """Override settings for test environment."""
    return Settings(
        app_env="testing",
        debug=True,
        jwt_secret_key="test-secret-key-for-testing-only-do-not-use-in-production-min-32-chars",
        jwt_access_token_expire_minutes=5,
        jwt_refresh_token_expire_days=1,
        max_login_attempts=5,
        account_lockout_minutes=15,
    )


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provide test settings fixture."""
    return get_test_settings()


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Create all database tables before test, drop afterwards."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session for a test."""
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(test_settings: Settings, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async test client for FastAPI application with DB dependency override."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
