"""
MedFusion AI — User ORM Model.

Stores user credentials, roles, profile metadata, and account security flags:
- Role-based authorization (Admin, Clinician, Radiologist, Auditor)
- Account lockout tracking (failed login attempts, locked_until)
- UUID primary key and timestamp tracking
"""

import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    """System roles defining permission boundaries."""
    ADMIN = "admin"
    CLINICIAN = "clinician"
    RADIOLOGIST = "radiologist"
    AUDITOR = "auditor"


class User(Base, UUIDMixin, TimestampMixin):
    """User account entity for authentication and RBAC."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_type=True),
        default=UserRole.CLINICIAN,
        nullable=False,
        index=True,
    )
    department: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Security & Account Lockout
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def is_locked(self, current_time: datetime) -> bool:
        """Check if account is currently locked out."""
        if self.locked_until and self.locked_until > current_time:
            return True
        return False

    def __repr__(self) -> str:
        return f"<User id={self.id} email='{self.email}' role='{self.role.value}'>"
