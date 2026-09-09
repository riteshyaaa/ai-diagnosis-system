"""
MedFusion AI — User Repository.

Encapsulates all database operations on the User entity:
- Lookups by email and ID
- Failed login tracking & lockout management
- Role-based filtering
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """User repository providing specialized queries for authentication and user management."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Lookup a user by unique lowercase email."""
        stmt = select(User).where(User.email == email.lower().strip())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def record_failed_login(
        self,
        user: User,
        max_attempts: int = 5,
        lockout_duration_seconds: int = 900,
    ) -> User:
        """
        Increment failed login attempt counter and lock account if threshold exceeded.
        """
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= max_attempts:
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            user.locked_until = now + timedelta(seconds=lockout_duration_seconds)

        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def reset_failed_logins(self, user: User) -> User:
        """
        Reset failed login counter, clear lockout status, and record login timestamp.
        """
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(user)
        return user
