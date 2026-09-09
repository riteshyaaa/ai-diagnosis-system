"""
MedFusion AI — JWT Token Security Unit Tests.
"""

from datetime import timedelta
import pytest
from app.exceptions import AuthenticationError
from app.security.jwt import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    verify_token_type,
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
)


def test_create_and_decode_access_token():
    """Verify access token creation contains expected claims."""
    user_id = "12345678-1234-5678-1234-567812345678"
    email = "doctor@hospital.org"
    role = "clinician"

    token = create_access_token(user_id=user_id, email=email, role=role)
    payload = decode_token(token)

    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload["role"] == role
    assert payload["type"] == ACCESS_TOKEN_TYPE
    assert "exp" in payload
    assert "iat" in payload


def test_create_and_decode_refresh_token():
    """Verify refresh token creation contains minimal payload."""
    user_id = "12345678-1234-5678-1234-567812345678"

    token = create_refresh_token(user_id=user_id)
    payload = decode_token(token)

    assert payload["sub"] == user_id
    assert payload["type"] == REFRESH_TOKEN_TYPE
    assert "exp" in payload


def test_create_token_pair():
    """Verify create_token_pair returns both valid tokens."""
    tokens = create_token_pair(
        user_id="12345678-1234-5678-1234-567812345678",
        email="doctor@hospital.org",
        role="radiologist",
    )

    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] > 0

    access_payload = decode_token(tokens["access_token"])
    refresh_payload = decode_token(tokens["refresh_token"])

    verify_token_type(access_payload, ACCESS_TOKEN_TYPE)
    verify_token_type(refresh_payload, REFRESH_TOKEN_TYPE)


def test_decode_expired_token():
    """Verify expired token raises AuthenticationError."""
    token = create_access_token(
        user_id="12345678-1234-5678-1234-567812345678",
        email="doc@hospital.org",
        role="clinician",
        expires_delta=timedelta(seconds=-10),  # expired 10s ago
    )

    with pytest.raises(AuthenticationError):
        decode_token(token)


def test_verify_token_type_mismatch_raises_error():
    """Verify that using access token where refresh token is expected fails."""
    token = create_access_token(
        user_id="12345678-1234-5678-1234-567812345678",
        email="doc@hospital.org",
        role="clinician",
    )
    payload = decode_token(token)

    with pytest.raises(AuthenticationError):
        verify_token_type(payload, REFRESH_TOKEN_TYPE)
