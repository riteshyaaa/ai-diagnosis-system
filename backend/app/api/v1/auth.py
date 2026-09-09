"""
MedFusion AI — Authentication API Endpoints (v1).

Exposes routes for:
- POST /login: Authenticate credentials, issue tokens
- POST /refresh: Rotate refresh token, issue new token pair
- POST /register: Create new clinician/radiologist account
- GET  /me: Fetch currently authenticated user profile
- POST /change-password: Change own password
- POST /logout: Terminate session
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenRefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserPasswordChange, UserResponse
from app.security.dependencies import get_current_user
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate with email and password to obtain JWT access and refresh tokens.",
)
async def login(
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return token pair."""
    auth_service = AuthService(session)
    return await auth_service.authenticate(login_data)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
    description="Exchange a valid refresh token for a rotated new access and refresh token pair.",
)
async def refresh_tokens(
    refresh_data: TokenRefreshRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Rotate refresh token and issue new token pair."""
    auth_service = AuthService(session)
    return await auth_service.refresh_tokens(refresh_data.refresh_token)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Account",
    description="Register a new healthcare professional account.",
)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user account."""
    auth_service = AuthService(session)
    return await auth_service.register_user(user_data)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
    description="Retrieve profile details for the currently authenticated user.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return profile of currently logged-in user."""
    return UserResponse.model_validate(current_user)


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change Password",
    description="Update password for the currently authenticated user.",
)
async def change_password(
    password_data: UserPasswordChange,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update current user's password."""
    auth_service = AuthService(session)
    await auth_service.change_password(current_user.id, password_data)
    return {"message": "Password changed successfully."}


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Log out the current user session.",
)
async def logout(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Client-side token disposal confirmation."""
    return {"message": "Successfully logged out."}
