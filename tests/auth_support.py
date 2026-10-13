"""Test-only helpers for users that must not be self-registered."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.security.password import hash_password


async def login_as_provisioned_role(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    role: UserRole,
    email: str,
    full_name: str,
    password: str = "AuditSecure2026!",
) -> str:
    """Provision a non-self-service role in the test database and return its token."""
    db_session.add(
        User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
            is_verified=True,
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
