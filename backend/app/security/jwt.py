"""
MedFusion AI — JWT Token Management.

Handles generation, validation, and decoding of access and refresh tokens.
- Short-lived Access Tokens (default 30 min) for API authorization
- Long-lived Refresh Tokens (default 7 days) with rotation support
- Includes token type ('access' or 'refresh'), subject (user_id), and role
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from jose import JWTError, jwt

from app.config import get_settings
from app.exceptions import AuthenticationError

settings = get_settings()

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def create_token(
    data: Dict[str, Any],
    token_type: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT token with standard claims.

    Args:
        data: Custom claims to embed (e.g. sub, email, role).
        token_type: Type of token ('access' or 'refresh').
        expires_delta: Custom expiration duration, or uses settings default.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    elif token_type == ACCESS_TOKEN_TYPE:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    elif token_type == REFRESH_TOKEN_TYPE:
        expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    else:
        expire = now + timedelta(minutes=15)

    to_encode.update(
        {
            "type": token_type,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "iss": settings.app_name,
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a short-lived access token."""
    claims = {
        "sub": user_id,
        "email": email,
        "role": role,
    }
    return create_token(claims, token_type=ACCESS_TOKEN_TYPE, expires_delta=expires_delta)


def create_refresh_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a long-lived refresh token."""
    claims = {
        "sub": user_id,
    }
    return create_token(claims, token_type=REFRESH_TOKEN_TYPE, expires_delta=expires_delta)


def create_token_pair(
    user_id: str,
    email: str,
    role: str,
) -> Dict[str, Any]:
    """
    Generate both access and refresh tokens.

    Returns:
        Dictionary containing access_token, refresh_token, token_type, and expires_in seconds.
    """
    access_token = create_access_token(user_id=user_id, email=email, role=role)
    refresh_token = create_refresh_token(user_id=user_id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token signature and expiration.

    Args:
        token: JWT string.

    Returns:
        Decoded payload dictionary.

    Raises:
        AuthenticationError: If token is invalid, expired, or signature doesn't match.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid or expired token: {str(e)}")


def verify_token_type(payload: Dict[str, Any], expected_type: str) -> None:
    """
    Ensure the token payload matches the expected token type (access vs refresh).

    Raises:
        AuthenticationError: If token type is invalid or mismatched.
    """
    token_type = payload.get("type")
    if not token_type or token_type != expected_type:
        raise AuthenticationError(
            f"Invalid token type: expected '{expected_type}', got '{token_type}'"
        )
