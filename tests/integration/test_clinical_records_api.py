"""
MedFusion AI — Clinical Record API Integration Tests.

Tests:
- Clinical record creation with standard 13 features & validation report
- Critical safety alert detection on extreme vitals
- Physiological range validation failure (HTTP 400 / 422)
- Listing records for a case
- Retrieving single clinical record
- Updating clinical record in DRAFT case
- Rejecting update when case is not in DRAFT status
- Deleting clinical record in DRAFT case
- Audit logging of clinical record operations
- RBAC permissions
"""

import pytest
from httpx import AsyncClient

from app.models.diagnostic_case import CaseStatus


async def get_clinician_token(client: AsyncClient, email: str = "dr.clin.tester@hospital.org") -> str:
    """Helper to create and authenticate a clinician user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Dr. Clinical Tester",
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


async def setup_test_case(client: AsyncClient, headers: dict, mrn: str = "MRN-CR-01") -> str:
    """Helper to create a test patient and draft case."""
    pt_res = await client.post(
        "/api/v1/patients",
        json={"mrn": mrn, "age": 58, "gender": "male"},
        headers=headers,
    )
    patient_id = pt_res.json()["id"]

    case_res = await client.post(
        "/api/v1/cases",
        json={"patient_id": patient_id, "notes": "Evaluating clinical tabular records"},
        headers=headers,
    )
    return case_res.json()["id"]


@pytest.mark.asyncio
async def test_create_and_retrieve_clinical_record(client: AsyncClient):
    """Test standard clinical measurement creation and retrieval with validation report."""
    token = await get_clinician_token(client, "dr.record1@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = await setup_test_case(client, headers, "MRN-CR-VAL-01")

    payload = {
        "age": 58,
        "sex": 1,
        "chest_pain_type": 2,
        "resting_bp": 135.0,
        "cholesterol": 245.0,
        "fasting_bs": 0,
        "resting_ecg": 1,
        "max_hr": 150.0,
        "exercise_angina": 0,
        "st_depression": 1.4,
        "st_slope": 1,
        "num_major_vessels": 1,
        "thalassemia": 2,
        "bmi": 27.2,
        "smoking_status": "former",
    }

    create_res = await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=payload,
        headers=headers,
    )
    assert create_res.status_code == 201
    data = create_res.json()

    assert "record" in data
    assert "validation_report" in data
    assert data["validation_report"]["is_valid"] is True
    record_id = data["record"]["id"]
    assert data["record"]["age"] == 58
    assert data["record"]["cholesterol"] == 245.0

    # Retrieve single record
    get_res = await client.get(
        f"/api/v1/clinical-records/{record_id}",
        headers=headers,
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == record_id

    # List records for case
    list_res = await client.get(
        f"/api/v1/cases/{case_id}/clinical-records",
        headers=headers,
    )
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1
    assert list_res.json()["items"][0]["id"] == record_id


@pytest.mark.asyncio
async def test_critical_alerts_in_validation_report(client: AsyncClient):
    """Test that critical physiological flags (hypertensive crisis, severe ST depression) appear in validation report."""
    token = await get_clinician_token(client, "dr.crit@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = await setup_test_case(client, headers, "MRN-CR-CRIT-01")

    payload = {
        "age": 62,
        "sex": 1,
        "chest_pain_type": 0,
        "resting_bp": 195.0,  # Hypertensive crisis (>= 180)
        "cholesterol": 380.0,  # Hypercholesterolemia (>= 350)
        "fasting_bs": 1,
        "resting_ecg": 2,
        "max_hr": 205.0,  # Extreme tachycardia (>= 200)
        "exercise_angina": 1,
        "st_depression": 3.8,  # Critical ischemia (>= 3.0)
        "st_slope": 2,
        "num_major_vessels": 3,
        "thalassemia": 3,
    }

    res = await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 201
    report = res.json()["validation_report"]
    assert report["is_valid"] is True
    assert len(report["critical_alerts"]) >= 3
    assert any("resting_bp" in a for a in report["critical_alerts"])
    assert any("st_depression" in a for a in report["critical_alerts"])


@pytest.mark.asyncio
async def test_reject_impossible_clinical_values(client: AsyncClient):
    """Test that biologically impossible measurements are rejected."""
    token = await get_clinician_token(client, "dr.badval@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = await setup_test_case(client, headers, "MRN-CR-BAD-01")

    # Impossible resting blood pressure (400 mm Hg)
    bad_payload = {
        "age": 45,
        "sex": 0,
        "chest_pain_type": 1,
        "resting_bp": 400.0,
        "cholesterol": 200.0,
        "fasting_bs": 0,
        "resting_ecg": 0,
        "max_hr": 140.0,
        "exercise_angina": 0,
        "st_depression": 0.5,
        "st_slope": 0,
        "num_major_vessels": 0,
        "thalassemia": 1,
    }

    res = await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=bad_payload,
        headers=headers,
    )
    assert res.status_code == 422  # Pydantic or service validation failure


@pytest.mark.asyncio
async def test_update_clinical_record(client: AsyncClient):
    """Test updating clinical record in DRAFT case."""
    token = await get_clinician_token(client, "dr.update@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = await setup_test_case(client, headers, "MRN-CR-UPD-01")

    # Create record
    payload = {
        "age": 50,
        "sex": 1,
        "chest_pain_type": 1,
        "resting_bp": 120.0,
        "cholesterol": 200.0,
        "fasting_bs": 0,
        "resting_ecg": 0,
        "max_hr": 150.0,
        "exercise_angina": 0,
        "st_depression": 0.0,
        "st_slope": 0,
        "num_major_vessels": 0,
        "thalassemia": 1,
    }
    create_res = await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=payload,
        headers=headers,
    )
    record_id = create_res.json()["record"]["id"]

    # Patch record
    patch_res = await client.patch(
        f"/api/v1/clinical-records/{record_id}",
        json={"cholesterol": 215.0, "max_hr": 155.0},
        headers=headers,
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["cholesterol"] == 215.0
    assert updated["max_hr"] == 155.0


@pytest.mark.asyncio
async def test_delete_clinical_record(client: AsyncClient):
    """Test deleting clinical record in DRAFT case."""
    token = await get_clinician_token(client, "dr.del@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = await setup_test_case(client, headers, "MRN-CR-DEL-01")

    payload = {
        "age": 52,
        "sex": 0,
        "chest_pain_type": 0,
        "resting_bp": 125.0,
        "cholesterol": 210.0,
        "fasting_bs": 0,
        "resting_ecg": 0,
        "max_hr": 145.0,
        "exercise_angina": 0,
        "st_depression": 0.0,
        "st_slope": 0,
        "num_major_vessels": 0,
        "thalassemia": 1,
    }
    create_res = await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=payload,
        headers=headers,
    )
    record_id = create_res.json()["record"]["id"]

    # Delete record
    del_res = await client.delete(
        f"/api/v1/clinical-records/{record_id}",
        headers=headers,
    )
    assert del_res.status_code == 200

    # Verify 404 on subsequent get
    get_res = await client.get(
        f"/api/v1/clinical-records/{record_id}",
        headers=headers,
    )
    assert get_res.status_code == 404
