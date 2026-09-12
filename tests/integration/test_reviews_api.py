"""
MedFusion AI — Clinical Review & Human-in-the-Loop Integration Tests.

Comprehensive test suite verifying:
- Clinician review submission workflows (ACCEPT, MODIFY, REJECT)
- Case lifecycle state machine transition to REVIEWED status
- Mandatory modified diagnosis validation when decision is MODIFY
- Mandatory physician clinical notes rationale logging
- AI vs Clinician concordance metrics and aggregate statistics computation
- Case-level and Prediction-level review retrieval
- Role-based access control (RBAC) enforcement on review submission
- Mandatory regulatory CDSS disclaimer inclusion
"""

import io
import pytest
from PIL import Image
from httpx import AsyncClient

from tests.unit.test_image_processing import create_synthetic_radiograph


def make_png_bytes(width: int = 256, height: int = 256) -> bytes:
    """Generate synthetic radiograph encoded as PNG bytes."""
    arr = create_synthetic_radiograph(width, height)
    pil_img = Image.fromarray(arr)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


async def get_clinician_token(client: AsyncClient, email: str = "dr.review.tester@hospital.org") -> str:
    """Create and authenticate a clinician user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Dr. Clinical Reviewer",
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


async def get_auditor_token(client: AsyncClient, email: str = "auditor.review@hospital.org") -> str:
    """Create and authenticate an auditor user."""
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


def get_sample_clinical_payload() -> dict:
    """Return standard valid clinical telemetry."""
    return {
        "age": 62,
        "sex": 1,
        "chest_pain_type": 2,
        "resting_bp": 138.0,
        "cholesterol": 240.0,
        "fasting_bs": 0,
        "resting_ecg": 1,
        "max_hr": 145.0,
        "exercise_angina": 0,
        "st_depression": 1.6,
        "st_slope": 1,
        "num_major_vessels": 1,
        "thalassemia": 2,
        "source": "manual_entry",
    }


async def setup_case_with_prediction(client: AsyncClient, headers: dict, mrn: str = "MRN-REV-001") -> dict:
    """Helper to create patient, case, upload data, and run AI prediction."""
    # 1. Patient
    p_res = await client.post(
        "/api/v1/patients",
        json={"mrn": mrn, "age": 62, "sex": "male"},
        headers=headers,
    )
    patient_id = p_res.json()["id"]

    # 2. Case
    c_res = await client.post(
        "/api/v1/cases",
        json={
            "patient_id": patient_id,
            "modality": "multimodal",
            "chief_complaint": "Atypical chest tightness and mild fatigue",
            "priority": "routine",
        },
        headers=headers,
    )
    case_id = c_res.json()["id"]

    # 3. Image
    png_bytes = make_png_bytes(256, 256)
    files = {"file": ("radiograph.png", png_bytes, "image/png")}
    data = {"image_type": "chest_xray_pa"}
    await client.post(f"/api/v1/cases/{case_id}/images", files=files, data=data, headers=headers)

    # 4. Clinical Record
    await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=get_sample_clinical_payload(),
        headers=headers,
    )

    # 5. Predict
    pred_res = await client.post(
        f"/api/v1/cases/{case_id}/predict",
        json={"generate_explainability": True},
        headers=headers,
    )
    assert pred_res.status_code == 201
    return {"case_id": case_id, "prediction": pred_res.json()}


@pytest.mark.asyncio
async def test_submit_accept_review_workflow(client: AsyncClient):
    """
    Test submitting an ACCEPT clinical review.
    Verifies:
    - Case transitions to REVIEWED
    - Concordance is marked as True
    - Physician rationale and reviewer identity are recorded
    - Mandatory regulatory disclaimer is present
    """
    token = await get_clinician_token(client, "dr.accept@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_case_with_prediction(client, headers, mrn="MRN-ACCEPT-01")
    case_id = setup_data["case_id"]
    prediction_id = setup_data["prediction"]["id"]

    review_payload = {
        "prediction_id": prediction_id,
        "decision": "accept",
        "clinical_notes": "Concur with AI assessment. Visual opacity and ECG telemetry support findings.",
    }

    res = await client.post(f"/api/v1/cases/{case_id}/reviews", json=review_payload, headers=headers)
    assert res.status_code == 201
    review = res.json()

    assert review["case_id"] == case_id
    assert review["prediction_id"] == prediction_id
    assert review["decision"] == "accept"
    assert review["modified_diagnosis"] is None
    assert review["concordance"] is True
    assert "Concur with AI assessment" in review["clinical_notes"]
    assert review["reviewer"]["email"] == "dr.accept@hospital.org"
    assert review["case_number"] is not None
    assert "assistive Clinical Decision Support System" in review["clinical_disclaimer"]

    # Verify Case Status transitioned to REVIEWED
    case_res = await client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert case_res.json()["status"] == "reviewed"


@pytest.mark.asyncio
async def test_submit_modify_review_workflow(client: AsyncClient):
    """
    Test submitting a MODIFY clinical review.
    Verifies:
    - Clinician provides corrected diagnosis
    - Concordance is marked as False
    - Modified diagnosis is stored
    - Case transitions to REVIEWED
    """
    token = await get_clinician_token(client, "dr.modify@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_case_with_prediction(client, headers, mrn="MRN-MODIFY-01")
    case_id = setup_data["case_id"]
    prediction_id = setup_data["prediction"]["id"]

    review_payload = {
        "prediction_id": prediction_id,
        "decision": "modify",
        "modified_diagnosis": "Cardiomegaly with Early Stage Congestive Failure",
        "clinical_notes": "Adjusted primary diagnosis due to borderline CTR ratio and elevated jugular venous pressure.",
    }

    res = await client.post(f"/api/v1/cases/{case_id}/reviews", json=review_payload, headers=headers)
    assert res.status_code == 201
    review = res.json()

    assert review["decision"] == "modify"
    assert review["modified_diagnosis"] == "Cardiomegaly with Early Stage Congestive Failure"
    assert review["concordance"] is False
    assert "Adjusted primary diagnosis" in review["clinical_notes"]

    # Verify Case Status is REVIEWED
    case_res = await client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert case_res.json()["status"] == "reviewed"


@pytest.mark.asyncio
async def test_modify_decision_without_modified_diagnosis_fails(client: AsyncClient):
    """Test that selecting MODIFY without providing a modified_diagnosis fails with 422."""
    token = await get_clinician_token(client, "dr.modfail@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_case_with_prediction(client, headers, mrn="MRN-MODFAIL-01")
    case_id = setup_data["case_id"]

    review_payload = {
        "decision": "modify",
        "modified_diagnosis": "",  # Empty
        "clinical_notes": "Attempting modification without providing revised finding.",
    }

    res = await client.post(f"/api/v1/cases/{case_id}/reviews", json=review_payload, headers=headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_submit_reject_review_workflow(client: AsyncClient):
    """Test submitting a REJECT review with clinical reasoning."""
    token = await get_clinician_token(client, "dr.reject@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_case_with_prediction(client, headers, mrn="MRN-REJECT-01")
    case_id = setup_data["case_id"]
    prediction_id = setup_data["prediction"]["id"]

    review_payload = {
        "prediction_id": prediction_id,
        "decision": "reject",
        "clinical_notes": "AI predicted high risk, but patient has non-cardiac artifact and recent muscular strain.",
    }

    res = await client.post(f"/api/v1/cases/{case_id}/reviews", json=review_payload, headers=headers)
    assert res.status_code == 201
    review = res.json()

    assert review["decision"] == "reject"
    assert review["concordance"] is False
    assert "patient has non-cardiac artifact" in review["clinical_notes"]


@pytest.mark.asyncio
async def test_review_on_case_without_predictions_fails(client: AsyncClient):
    """Test that submitting a review on an empty case without predictions fails."""
    token = await get_clinician_token(client, "dr.nopred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    # Create patient & case only
    p_res = await client.post("/api/v1/patients", json={"mrn": "MRN-NOPRED-01", "age": 45, "sex": "female"}, headers=headers)
    patient_id = p_res.json()["id"]
    c_res = await client.post("/api/v1/cases", json={"patient_id": patient_id, "modality": "multimodal"}, headers=headers)
    case_id = c_res.json()["id"]

    res = await client.post(
        f"/api/v1/cases/{case_id}/reviews",
        json={"decision": "accept", "clinical_notes": "Reviewing empty case prematurely."},
        headers=headers,
    )
    assert res.status_code == 422
    assert "no AI predictions" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_case_reviews_and_prediction_reviews(client: AsyncClient):
    """Test retrieving reviews filtered by case and prediction."""
    token = await get_clinician_token(client, "dr.listrev@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_case_with_prediction(client, headers, mrn="MRN-LISTREV-01")
    case_id = setup_data["case_id"]
    prediction_id = setup_data["prediction"]["id"]

    # Submit review
    post_res = await client.post(
        f"/api/v1/cases/{case_id}/reviews",
        json={
            "prediction_id": prediction_id,
            "decision": "accept",
            "clinical_notes": "Verified against radiological markers and clinical history.",
        },
        headers=headers,
    )
    review_id = post_res.json()["id"]

    # 1. Fetch by case
    case_revs = await client.get(f"/api/v1/cases/{case_id}/reviews", headers=headers)
    assert case_revs.status_code == 200
    assert case_revs.json()["total"] >= 1
    assert case_revs.json()["items"][0]["id"] == review_id

    # 2. Fetch by prediction
    pred_revs = await client.get(f"/api/v1/predictions/{prediction_id}/reviews", headers=headers)
    assert pred_revs.status_code == 200
    assert pred_revs.json()["total"] >= 1
    assert pred_revs.json()["items"][0]["id"] == review_id

    # 3. Fetch single review by ID
    single_rev = await client.get(f"/api/v1/reviews/{review_id}", headers=headers)
    assert single_rev.status_code == 200
    assert single_rev.json()["id"] == review_id


@pytest.mark.asyncio
async def test_get_review_statistics_and_concordance_analytics(client: AsyncClient):
    """Test aggregate concordance statistics across multiple reviews."""
    token = await get_clinician_token(client, "dr.stats@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    # Create Case 1 -> Accept
    s1 = await setup_case_with_prediction(client, headers, mrn="MRN-STAT-01")
    await client.post(
        f"/api/v1/cases/{s1['case_id']}/reviews",
        json={"decision": "accept", "clinical_notes": "Accepting AI findings unconditionally."},
        headers=headers,
    )

    # Create Case 2 -> Modify
    s2 = await setup_case_with_prediction(client, headers, mrn="MRN-STAT-02")
    await client.post(
        f"/api/v1/cases/{s2['case_id']}/reviews",
        json={
            "decision": "modify",
            "modified_diagnosis": "Pleural Effusion with Infiltration",
            "clinical_notes": "Modifying to include secondary infiltration.",
        },
        headers=headers,
    )

    res = await client.get("/api/v1/reviews/stats", headers=headers)
    assert res.status_code == 200
    stats = res.json()

    assert stats["total_reviews"] >= 2
    assert stats["accepted_count"] >= 1
    assert stats["modified_count"] >= 1
    assert 0.0 <= stats["concordance_rate"] <= 100.0
    assert 0.0 <= stats["modification_rate"] <= 100.0
    assert len(stats["top_modified_diagnoses"]) > 0
    assert len(stats["recent_reviews"]) > 0
    assert "assistive Clinical Decision Support System" in stats["clinical_disclaimer"]


@pytest.mark.asyncio
async def test_submit_review_rbac_enforcement(client: AsyncClient):
    """Verify that non-clinical roles (e.g. auditor) cannot submit clinical reviews."""
    clinician_token = await get_clinician_token(client, "dr.rbac.owner2@hospital.org")
    clinician_headers = {"Authorization": f"Bearer {clinician_token}"}
    setup_data = await setup_case_with_prediction(client, clinician_headers, mrn="MRN-RBAC-REV-01")
    case_id = setup_data["case_id"]

    # Auditor attempting review submission
    auditor_token = await get_auditor_token(client, "auditor.rbac.rev@hospital.org")
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    res = await client.post(
        f"/api/v1/cases/{case_id}/reviews",
        json={"decision": "accept", "clinical_notes": "Auditor attempting unauthorized clinical review."},
        headers=auditor_headers,
    )
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"]
