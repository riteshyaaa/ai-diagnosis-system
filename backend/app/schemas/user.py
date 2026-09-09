"""
MedFusion AI — User Schemas.

Pydantic models for user creation, update, and response serialization.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user fields."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    role: UserRole = UserRole.CLINICIAN
    department: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    """Payload for creating a new user account."""
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Payload for updating user profile."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserPasswordChange(BaseModel):
    """Payload for user password change."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserResponse(UserBase):
    """Public user response schema (excludes password and security internals)."""
    id: UUID
    is_active: bool
    is_verified: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
