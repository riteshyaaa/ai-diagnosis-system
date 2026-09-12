"""
MedFusion AI — Patient Management API Integration Tests.

Tests:
- Patient creation with raw MRN (SHA-256 hashing)
- Duplicate MRN rejection (409 Conflict)
- Patient demographic filtering & pagination
- Patient retrieval by UUID and MRN search
- Patient demographic updates (PATCH)
- Role-based access control (RBAC) enforcement
"""

import pytest
from httpx import AsyncClient


async def get_clinician_token(client: AsyncClient, email: str = "dr.patient.test@hospital.org") -> str:
    """Helper to create and authenticate a clinician user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Dr. Patient Tester",
            "password": "DocSecure2026!",
            "role": "clinician",
            "department": "Cardiology",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "DocSecure2026!"},
    )
    return login_res.json()["access_token"]


async def get_auditor_token(client: AsyncClient, email: str = "auditor.patient@hospital.org") -> str:
    """Helper to create and authenticate an auditor user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Compliance Auditor",
            "password": "AuditSecure2026!",
            "role": "auditor",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "AuditSecure2026!"},
    )
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_patient_create_and_privacy_hashing(client: AsyncClient):
    """Verify patient registration computes SHA-256 hash and does not leak raw MRN."""
    token = await get_clinician_token(client, "dr.cx@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "mrn": "MRN-2026-X998811",
        "age": 62,
        "sex": "female",
        "blood_group": "A+",
        "medical_history_summary": "Chronic stable angina, hyperlipidemia.",
    }
    res = await client.post("/api/v1/patients", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert "id" in data
    assert "mrn_hash" in data
    assert len(data["mrn_hash"]) == 64
    assert "mrn" not in data  # Privacy check: raw MRN is never returned
    assert data["age"] == 62
    assert data["sex"] == "female"
    assert data["blood_group"] == "A+"
    assert data["medical_history_summary"] == "Chronic stable angina, hyperlipidemia."


@pytest.mark.asyncio
async def test_duplicate_patient_mrn_rejected(client: AsyncClient):
    """Verify duplicate MRN returns 409 Conflict."""
    token = await get_clinician_token(client, "dr.dup@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "mrn": "MRN-DUP-001",
        "age": 45,
        "sex": "male",
    }
    res1 = await client.post("/api/v1/patients", json=payload, headers=headers)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/patients", json=payload, headers=headers)
    assert res2.status_code == 409
    assert "already exists" in res2.text.lower()


@pytest.mark.asyncio
async def test_patient_list_filtering_and_pagination(client: AsyncClient):
    """Verify demographic filtering (sex, age range) and pagination."""
    token = await get_clinician_token(client, "dr.filter@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    # Seed 3 patients
    p1 = {"mrn": "MRN-FILTER-01", "age": 30, "sex": "female"}
    p2 = {"mrn": "MRN-FILTER-02", "age": 55, "sex": "female"}
    p3 = {"mrn": "MRN-FILTER-03", "age": 70, "sex": "male"}

    for p in [p1, p2, p3]:
        res = await client.post("/api/v1/patients", json=p, headers=headers)
        assert res.status_code == 201

    # Filter by sex=female
    res_female = await client.get("/api/v1/patients?sex=female", headers=headers)
    assert res_female.status_code == 200
    females = res_female.json()
    assert females["total"] == 2
    assert len(females["items"]) == 2

    # Filter by age range 50-75
    res_age = await client.get("/api/v1/patients?min_age=50&max_age=75", headers=headers)
    assert res_age.status_code == 200
    aged = res_age.json()
    assert aged["total"] == 2
    ages = [item["age"] for item in aged["items"]]
    assert 55 in ages
    assert 70 in ages


@pytest.mark.asyncio
async def test_patient_get_by_id_and_mrn_search(client: AsyncClient):
    """Verify retrieval by UUID and lookup via raw MRN."""
    token = await get_clinician_token(client, "dr.search@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await client.post(
        "/api/v1/patients",
        json={"mrn": "MRN-SEARCH-999", "age": 50, "sex": "male"},
        headers=headers,
    )
    patient_id = create_res.json()["id"]

    # Lookup by ID
    get_res = await client.get(f"/api/v1/patients/{patient_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == patient_id

    # Search by raw MRN
    search_res = await client.get("/api/v1/patients/search/mrn?mrn=MRN-SEARCH-999", headers=headers)
    assert search_res.status_code == 200
    assert search_res.json()["id"] == patient_id

    # Search non-existent MRN
    missing_search = await client.get("/api/v1/patients/search/mrn?mrn=DOES_NOT_EXIST", headers=headers)
    assert missing_search.status_code == 404


@pytest.mark.asyncio
async def test_patient_patch_update(client: AsyncClient):
    """Verify demographic updates via PATCH."""
    token = await get_clinician_token(client, "dr.patch@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await client.post(
        "/api/v1/patients",
        json={"mrn": "MRN-PATCH-001", "age": 40, "sex": "unknown"},
        headers=headers,
    )
    patient_id = create_res.json()["id"]

    patch_payload = {
        "age": 41,
        "sex": "female",
        "blood_group": "B+",
        "medical_history_summary": "Updated notes: diagnosed with mild hypertension.",
    }
    patch_res = await client.patch(f"/api/v1/patients/{patient_id}", json=patch_payload, headers=headers)
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["age"] == 41
    assert updated["sex"] == "female"
    assert updated["blood_group"] == "B+"
    assert updated["medical_history_summary"] == "Updated notes: diagnosed with mild hypertension."


@pytest.mark.asyncio
async def test_patient_rbac_enforcement(client: AsyncClient):
    """Verify that unauthorized requests and non-clinicians cannot register patients."""
    # 1. No token -> 401
    res_no_auth = await client.post("/api/v1/patients", json={"mrn": "MRN-UNAUTH-01"})
    assert res_no_auth.status_code == 401

    # 2. Auditor token cannot create patient (requires clinician or admin) -> 403
    auditor_token = await get_auditor_token(client, "auditor.rbac@hospital.org")
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}
    res_forbidden = await client.post(
        "/api/v1/patients",
        json={"mrn": "MRN-FORBIDDEN-01"},
        headers=auditor_headers,
    )
    assert res_forbidden.status_code == 403
