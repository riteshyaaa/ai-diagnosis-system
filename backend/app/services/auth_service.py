"""
MedFusion AI — Authentication & User Management Service.

Encapsulates business logic for authentication, session lifecycle,
account lockouts, registration, and credential security.
"""

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import (
    AccountLockedError,
    AuthenticationError,
    AuthorizationError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserPasswordChange, UserResponse
from app.security.jwt import (
    create_token_pair,
    decode_token,
    verify_token_type,
    REFRESH_TOKEN_TYPE,
)
from app.security.password import hash_password, is_password_strong, verify_password

settings = get_settings()


class AuthService:
    """Authentication and user lifecycle service."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def authenticate(self, login_data: LoginRequest) -> TokenResponse:
        """
        Authenticate a user by email and password with brute-force protection.

        - Checks if account is locked out
        - Verifies bcrypt password hash
        - On failure: increments counter, locks after max_attempts
        - On success: resets counter, issues JWT access + refresh token pair
        """
        user = await self.user_repo.get_by_email(login_data.email)
        if not user:
            # Constant-time comparison simulation to prevent email enumeration timing attacks
            verify_password("dummy_password", "$2b$12$e8Yd8h1zZ3ZkG7uL.7mU.e8Yd8h1zZ3ZkG7uL.7mU.e8Yd8h1zZ3Zk")
            raise AuthenticationError("Invalid email or password.")

        now = datetime.now(timezone.utc)
        if user.is_locked(now):
            locked_until = user.locked_until
            if locked_until and locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            remaining_seconds = (locked_until - now).total_seconds() if locked_until else 0
            remaining_minutes = max(1, int(remaining_seconds / 60) + 1)
            raise AccountLockedError(
                f"Account is locked due to too many failed attempts. Try again in {remaining_minutes} minutes."
            )

        if not user.is_active:
            raise AuthorizationError("Account is inactive. Contact the system administrator.")

        if not verify_password(login_data.password, user.hashed_password):
            await self.user_repo.record_failed_login(
                user,
                max_attempts=settings.max_login_attempts,
                lockout_duration_seconds=settings.account_lockout_minutes * 60,
            )
            attempts_left = max(0, settings.max_login_attempts - user.failed_login_attempts)
            if attempts_left == 0:
                raise AccountLockedError(
                    f"Account locked for {settings.account_lockout_minutes} minutes due to multiple failed attempts."
                )
            raise AuthenticationError(
                f"Invalid email or password. {attempts_left} attempts remaining before account lockout."
            )

        # Successful login: reset failed counters and update last_login
        await self.user_repo.reset_failed_logins(user)

        tokens = create_token_pair(
            user_id=str(user.id),
            email=user.email,
            role=user.role.value,
        )

        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type="bearer",
            expires_in=tokens["expires_in"],
            user=UserResponse.model_validate(user),
        )

    async def refresh_tokens(self, refresh_token_str: str) -> TokenResponse:
        """
        Exchange a valid refresh token for a new access + refresh token pair (token rotation).
        """
        payload = decode_token(refresh_token_str)
        verify_token_type(payload, REFRESH_TOKEN_TYPE)

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationError("Invalid refresh token payload: missing subject.")

        try:
            user_id = UUID(user_id_str)
        except ValueError:
            raise AuthenticationError("Invalid user ID in token.")

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthenticationError("User associated with token no longer exists.")

        if not user.is_active:
            raise AuthorizationError("Account is inactive.")

        tokens = create_token_pair(
            user_id=str(user.id),
            email=user.email,
            role=user.role.value,
        )

        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type="bearer",
            expires_in=tokens["expires_in"],
            user=UserResponse.model_validate(user),
        )

    async def register_user(self, user_create: UserCreate) -> UserResponse:
        """
        Register a new user account with validated credentials.
        """
        # Validate password strength
        is_strong, err_msg = is_password_strong(user_create.password)
        if not is_strong:
            raise ValidationError(err_msg)

        # Check unique email
        existing_user = await self.user_repo.get_by_email(user_create.email)
        if existing_user:
            raise DuplicateError(f"User with email '{user_create.email}' already exists.")

        # Hash password and create entity
        hashed_pwd = hash_password(user_create.password)
        new_user = User(
            email=user_create.email.lower().strip(),
            hashed_password=hashed_pwd,
            full_name=user_create.full_name.strip(),
            role=user_create.role,
            department=user_create.department,
            is_active=True,
            is_verified=False,
        )

        created = await self.user_repo.create(new_user)
        return UserResponse.model_validate(created)

    async def change_password(
        self,
        user_id: UUID,
        password_data: UserPasswordChange,
    ) -> None:
        """
        Change an existing user's password after verifying the current password.
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found.")

        if not verify_password(password_data.current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect.")

        is_strong, err_msg = is_password_strong(password_data.new_password)
        if not is_strong:
            raise ValidationError(err_msg)

        user.hashed_password = hash_password(password_data.new_password)
        await self.user_repo.update(user)
