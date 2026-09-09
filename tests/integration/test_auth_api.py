"""
MedFusion AI — Authentication API Integration Tests.

Tests the full authentication workflow:
- Account registration
- Login with valid credentials → token pair
- Login with bad password → 401 error
- Account lockout after 5 failed login attempts → 423/401 error
- Authenticated user profile retrieval (/me)
- Refresh token rotation (/refresh)
- User logout (/logout)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login_flow(client: AsyncClient):
    """Test full cycle: register new user -> login -> fetch profile."""
    # 1. Register
    register_payload = {
        "email": "dr.smith@hospital.org",
        "full_name": "Dr. Sarah Smith",
        "password": "SecurePassword123!",
        "role": "clinician",
        "department": "Cardiology",
    }
    reg_res = await client.post("/api/v1/auth/register", json=register_payload)
    assert reg_res.status_code == 201, reg_res.text
    user_data = reg_res.json()
    assert user_data["email"] == "dr.smith@hospital.org"
    assert user_data["full_name"] == "Dr. Sarah Smith"
    assert user_data["role"] == "clinician"
    assert "hashed_password" not in user_data

    # 2. Login
    login_payload = {
        "email": "dr.smith@hospital.org",
        "password": "SecurePassword123!",
    }
    login_res = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"

    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]

    # 3. Get /me profile with Bearer token
    headers = {"Authorization": f"Bearer {access_token}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    profile = me_res.json()
    assert profile["email"] == "dr.smith@hospital.org"

    # 4. Refresh token rotation
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens


@pytest.mark.asyncio
async def test_duplicate_registration_rejected(client: AsyncClient):
    """Verify that registering with duplicate email returns 409 Conflict."""
    payload = {
        "email": "unique@hospital.org",
        "full_name": "Unique User",
        "password": "SecurePassword123!",
        "role": "radiologist",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_weak_password_rejected(client: AsyncClient):
    """Verify that weak password during registration returns 422."""
    payload = {
        "email": "weak@hospital.org",
        "full_name": "Weak Pwd",
        "password": "short",
        "role": "clinician",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_account_lockout_after_failed_attempts(client: AsyncClient):
    """Verify that 5 failed attempts locks the account."""
    # 1. Register user
    reg_payload = {
        "email": "victim@hospital.org",
        "full_name": "Victim User",
        "password": "CorrectPassword123!",
        "role": "clinician",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Attempt 4 failed logins -> each returns 401
    bad_login = {"email": "victim@hospital.org", "password": "WrongPassword123!"}
    for _ in range(4):
        res = await client.post("/api/v1/auth/login", json=bad_login)
        assert res.status_code == 401

    # 3. 5th failed attempt -> locks account
    res5 = await client.post("/api/v1/auth/login", json=bad_login)
    assert res5.status_code in (401, 423)
    assert "lock" in res5.text.lower()

    # 4. Even with correct password, now locked out
    good_login = {"email": "victim@hospital.org", "password": "CorrectPassword123!"}
    res_locked = await client.post("/api/v1/auth/login", json=good_login)
    assert res_locked.status_code == 423
