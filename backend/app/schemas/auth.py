"""
MedFusion AI — Authentication Schemas.

Pydantic models for login requests, token responses, and session payloads.
"""

from typing import Annotated, Optional
from pydantic import BaseModel, Field

from app.schemas.user import UserResponse

EmailType = Annotated[
    str,
    Field(
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="Valid email address",
    ),
]


class LoginRequest(BaseModel):
    """Payload for username/password authentication."""
    email: EmailType
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Payload returned on successful authentication."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Lifetime of access token in seconds
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    """Payload for exchanging a refresh token for a new token pair."""
    refresh_token: str = Field(..., min_length=1)


class TokenData(BaseModel):
    """Internal representation of decoded JWT claims."""
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    token_type: Optional[str] = None
