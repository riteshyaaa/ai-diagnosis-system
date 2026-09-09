"""
MedFusion AI — Security & RBAC Dependencies.

Provides FastAPI dependency functions for extracting and verifying:
- Current authenticated user via JWT Bearer token
- Role-based authorization requirements (Admin, Clinician, Radiologist, Auditor)
"""

from typing import Callable, List, Optional
from uuid import UUID
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import AuthenticationError, AuthorizationError
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.security.jwt import ACCESS_TOKEN_TYPE, decode_token, verify_token_type

# Bearer token extractor (auto-handles 403 on missing authorization header)
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate JWT access token from request Authorization header,
    then fetch and return the active User entity from the database.

    Raises:
        AuthenticationError: If header is missing, token invalid/expired, or user not found.
        AuthorizationError: If the account is deactivated.
    """
    if not credentials:
        raise AuthenticationError("Missing Authorization header with Bearer token.")

    payload = decode_token(credentials.credentials)
    verify_token_type(payload, ACCESS_TOKEN_TYPE)

    user_id_str: Optional[str] = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Token payload missing subject identifier.")

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise AuthenticationError("Malformed user ID in token.")

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise AuthenticationError("User associated with this token no longer exists.")

    if not user.is_active:
        raise AuthorizationError("Account is inactive.")

    return user


def require_roles(allowed_roles: List[UserRole]) -> Callable:
    """
    Dependency factory that restricts endpoint access to users possessing
    at least one of the specified roles.

    Args:
        allowed_roles: List of UserRole values permitted to access the endpoint.
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            role_names = ", ".join([r.value for r in allowed_roles])
            raise AuthorizationError(
                f"Access forbidden: requires one of the following roles: [{role_names}]. "
                f"Your role is '{current_user.role.value}'."
            )
        return current_user

    return role_checker


# Role convenience dependencies
require_admin = require_roles([UserRole.ADMIN])
require_clinician = require_roles([UserRole.ADMIN, UserRole.CLINICIAN])
require_radiologist = require_roles([UserRole.ADMIN, UserRole.RADIOLOGIST])
require_auditor = require_roles([UserRole.ADMIN, UserRole.AUDITOR])
require_clinical_staff = require_roles([UserRole.ADMIN, UserRole.CLINICIAN, UserRole.RADIOLOGIST])
