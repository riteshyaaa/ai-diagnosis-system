"""Seed hospital demo personas for explicitly enabled local development environments."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.security.password import hash_password

DEMO_PASSWORD = "MedFusion#2026Secure!"

DEMO_USERS = (
    ("dr.chen@medfusion.local", "Dr. Chen", UserRole.CLINICIAN, "Cardiology"),
    ("dr.patel@medfusion.local", "Dr. Patel", UserRole.RADIOLOGIST, "Radiology"),
    ("admin@medfusion.local", "Hospital Administrator", UserRole.ADMIN, "Compliance"),
)


async def seed_demo_users(session: AsyncSession) -> None:
    """Create any missing demo accounts without changing existing user credentials."""
    users = UserRepository(session)
    for email, full_name, role, department in DEMO_USERS:
        if await users.get_by_email(email):
            continue
        session.add(
            User(
                email=email,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name=full_name,
                role=role,
                department=department,
                is_active=True,
                is_verified=True,
            )
        )
    await session.flush()
