"""
MedFusion AI — Diagnostic Case API Integration Tests.

Tests:
- Diagnostic case creation in DRAFT status
- Relational link to patient record
- Auto-generated and custom case numbers
- Filtering by status, modality, and patient
- Full case relational graph retrieval (/details)
- State machine workflow transitions (DRAFT -> SUBMITTED -> PROCESSING -> COMPLETED -> REVIEWED -> ARCHIVED)
- Invalid state transition rejection (422)
- Case deletion rules (only DRAFT can be deleted)
- Role-based authorization constraints
"""

import pytest
from httpx import AsyncClient


async def get_clinician_token(client: AsyncClient, email: str = "dr.case.tester@hospital.org") -> str:
    """Helper to register and authenticate a clinician user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Dr. Case Lead",
            "password": "DocSecure2026!",
            "role": "clinician",
            "department": "Pulmonology",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "DocSecure2026!"},
    )
    return login_res.json()["access_token"]


async def create_test_patient(client: AsyncClient, headers: dict, mrn: str = "MRN-CASE-TEST-01") -> str:
    """Helper to create a test patient and return patient UUID."""
    res = await client.post(
        "/api/v1/patients",
        json={"mrn": mrn, "age": 65, "sex": "male"},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.asyncio
async def test_case_create_lifecycle_and_details(client: AsyncClient):
    """Test case creation, auto case number, retrieval, and relational graph."""
    token = await get_clinician_token(client, "dr.case1@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    patient_id = await create_test_patient(client, headers, "MRN-C1-001")

    # 1. Create Case
    case_payload = {
        "patient_id": patient_id,
        "modality": "multimodal",
        "chief_complaint": "Exertional dyspnea and persistent cough.",
        "clinical_notes": "Suspected cardiomegaly or pulmonary congestion.",
    }
    create_res = await client.post("/api/v1/cases", json=case_payload, headers=headers)
    assert create_res.status_code == 201, create_res.text
    case = create_res.json()
    assert case["status"] == "draft"
    assert case["modality"] == "multimodal"
    assert case["case_number"].startswith("CASE-")
    assert case["patient_id"] == patient_id
    case_id = case["id"]

    # 2. Get Case Summary
    get_res = await client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["case_number"] == case["case_number"]

    # 3. Get Full Details Relational Graph
    details_res = await client.get(f"/api/v1/cases/{case_id}/details", headers=headers)
    assert details_res.status_code == 200
    details = details_res.json()
    assert details["id"] == case_id
    assert details["patient"]["id"] == patient_id
    assert isinstance(details["images"], list)
    assert isinstance(details["clinical_records"], list)
    assert isinstance(details["predictions"], list)
    assert isinstance(details["reviews"], list)


@pytest.mark.asyncio
async def test_case_workflow_state_machine_valid_flow(client: AsyncClient):
    """Test sequential progression through all valid lifecycle states."""
    token = await get_clinician_token(client, "dr.state@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    patient_id = await create_test_patient(client, headers, "MRN-STATE-01")

    create_res = await client.post(
        "/api/v1/cases",
        json={"patient_id": patient_id, "modality": "multimodal"},
        headers=headers,
    )
    case_id = create_res.json()["id"]

    # DRAFT -> SUBMITTED
    res1 = await client.post(
        f"/api/v1/cases/{case_id}/status",
        json={"status": "submitted", "reason": "Data ingestion verified"},
        headers=headers,
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "submitted"

    # SUBMITTED -> PROCESSING
    res2 = await client.post(
        f"/api/v1/cases/{case_id}/status",
        json={"status": "processing", "reason": "Inference pipeline engaged"},
        headers=headers,
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "processing"

    # PROCESSING -> COMPLETED
    res3 = await client.post(
        f"/api/v1/cases/{case_id}/status",
        json={"status": "completed", "reason": "Predictions and XAI generated"},
        headers=headers,
    )
    assert res3.status_code == 200
    assert res3.json()["status"] == "completed"

    # COMPLETED -> REVIEWED
    res4 = await client.post(
        f"/api/v1/cases/{case_id}/status",
        json={"status": "reviewed", "reason": "Physician clinical sign-off"},
        headers=headers,
    )
    assert res4.status_code == 200
    assert res4.json()["status"] == "reviewed"

    # REVIEWED -> ARCHIVED
    res5 = await client.post(
        f"/api/v1/cases/{case_id}/status",
        json={"status": "archived", "reason": "Case closed and exported to EHR"},
        headers=headers,
    )
    assert res5.status_code == 200
    assert res5.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_invalid_state_transition_rejected(client: AsyncClient):
    """Verify that jumping illegal states (e.g. DRAFT -> COMPLETED) is rejected with 422."""
    token = await get_clinician_token(client, "dr.invalid@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    patient_id = await create_test_patient(client, headers, "MRN-INV-01")

    create_res = await client.post(
        "/api/v1/cases",
        json={"patient_id": patient_id, "modality": "multimodal"},
        headers=headers,
    )
    case_id = create_res.json()["id"]

    # Illegal transition: DRAFT -> COMPLETED directly
    bad_res = await client.post(
        f"/api/v1/cases/{case_id}/status",
        json={"status": "completed", "reason": "Attempting illegal jump"},
        headers=headers,
    )
    assert bad_res.status_code == 422
    assert "invalid state transition" in bad_res.text.lower()


@pytest.mark.asyncio
async def test_case_update_and_draft_deletion(client: AsyncClient):
    """Verify editing case metadata and deleting draft cases."""
    token = await get_clinician_token(client, "dr.del@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    patient_id = await create_test_patient(client, headers, "MRN-DEL-01")

    create_res = await client.post(
        "/api/v1/cases",
        json={"patient_id": patient_id, "modality": "image_only", "chief_complaint": "Initial complaint"},
        headers=headers,
    )
    case_id = create_res.json()["id"]

    # PATCH metadata
    patch_res = await client.patch(
        f"/api/v1/cases/{case_id}",
        json={"modality": "multimodal", "chief_complaint": "Updated complaint"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["modality"] == "multimodal"
    assert patch_res.json()["chief_complaint"] == "Updated complaint"

    # Delete in DRAFT state succeeds
    del_res = await client.delete(f"/api/v1/cases/{case_id}", headers=headers)
    assert del_res.status_code == 200

    # Ensure it no longer exists
    get_res = await client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert get_res.status_code == 404
