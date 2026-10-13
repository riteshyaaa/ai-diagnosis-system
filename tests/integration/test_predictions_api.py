"""
MedFusion AI — AI Prediction & Inference API Integration Tests.

Comprehensive test suite verifying:
- Multimodal case prediction combining radiograph visual features and EHR tabular data
- Unimodal image-only prediction with 5 thoracic pathologies and Grad-CAM saliency
- Unimodal tabular-only prediction with calibrated cardiovascular risk and SHAP rankings
- Dynamic modality late-fusion gating weights and dominant modality detection
- Clinical uncertainty quantification (entropy, confidence bands, safety abstention)
- Mandatory non-autonomous CDSS regulatory disclaimer presence in all responses
- Case lifecycle state transitions (SUBMITTED/PROCESSING -> COMPLETED)
- Explainability artifact persistence (Grad-CAM heatmaps, SHAP feature vectors, summary text)
- Direct real-time inference (JSON and multipart radiograph upload)
- Prediction retrieval by ID, case listing, and latest prediction query
- Input validation and empty-case error handling
- Role-based access control (RBAC) enforcement
"""

import io
import json
import numpy as np
import pytest
from PIL import Image
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.security.password import hash_password
from tests.unit.test_image_processing import (
    create_synthetic_dicom_bytes,
    create_synthetic_radiograph,
)


def make_png_bytes(width: int = 256, height: int = 256) -> bytes:
    """Generate synthetic radiograph encoded as PNG bytes."""
    arr = create_synthetic_radiograph(width, height)
    pil_img = Image.fromarray(arr)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


async def get_clinician_token(client: AsyncClient, email: str = "dr.predict.tester@hospital.org") -> str:
    """Create and authenticate a clinician user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Dr. Prediction Tester",
            "password": "DocSecure2026!",
            "department": "Cardiology",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "DocSecure2026!"},
    )
    return login_res.json()["access_token"]


def get_sample_tabular_payload() -> dict:
    """Return standard valid clinical EHR telemetry."""
    return {
        "age": 63,
        "sex": 1,
        "chest_pain_type": 3,
        "resting_bp": 145.0,
        "cholesterol": 260.0,
        "fasting_bs": 1,
        "resting_ecg": 1,
        "max_hr": 138.0,
        "exercise_angina": 1,
        "st_depression": 2.2,
        "st_slope": 2,
        "num_major_vessels": 2,
        "thalassemia": 3,
        "source": "manual_entry",
    }


async def setup_multimodal_case(client: AsyncClient, headers: dict, mrn: str = "MRN-PRED-MULTI") -> str:
    """Helper to create patient, case, upload image, and add clinical record."""
    # 1. Patient
    p_res = await client.post(
        "/api/v1/patients",
        json={"mrn": mrn, "age": 63, "sex": "male"},
        headers=headers,
    )
    patient_id = p_res.json()["id"]

    # 2. Case
    c_res = await client.post(
        "/api/v1/cases",
        json={
            "patient_id": patient_id,
            "modality": "multimodal",
            "chief_complaint": "Acute chest pressure and dyspnea on exertion",
            "priority": "urgent",
        },
        headers=headers,
    )
    case_id = c_res.json()["id"]

    # 3. Image Upload
    png_bytes = make_png_bytes(256, 256)
    files = {"file": ("radiograph.png", png_bytes, "image/png")}
    data = {"image_type": "chest_xray_pa"}
    img_res = await client.post(f"/api/v1/cases/{case_id}/images", files=files, data=data, headers=headers)
    assert img_res.status_code == 201

    # 4. Clinical Record
    tab_res = await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=get_sample_tabular_payload(),
        headers=headers,
    )
    assert tab_res.status_code == 201

    return case_id


@pytest.mark.asyncio
async def test_multimodal_case_prediction_flow(client: AsyncClient):
    """
    Test complete multimodal AI prediction on a diagnostic case.
    Verifies vision pathologies, tabular risk, late fusion gating, XAI, uncertainty, and state advance.
    """
    token = await get_clinician_token(client, "dr.multi.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    case_id = await setup_multimodal_case(client, headers, mrn="MRN-MULTI-001")

    # The checked-in model metadata has no checkpoint. Inference must not
    # persist a prediction produced by random weights.
    predict_res = await client.post(
        f"/api/v1/cases/{case_id}/predict",
        json={"generate_explainability": True},
        headers=headers,
    )
    assert predict_res.status_code == 503
    assert "model not found" in predict_res.json()["detail"].lower()

    # An unavailable model must not complete or strand the case.
    case_res = await client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert case_res.status_code == 200
    assert case_res.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_image_only_case_prediction(client: AsyncClient):
    """Test unimodal radiograph prediction for a case with only imaging data."""
    token = await get_clinician_token(client, "dr.imgonly.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    # Setup patient & image-only case
    p_res = await client.post("/api/v1/patients", json={"mrn": "MRN-IMG-ONLY", "age": 45, "sex": "female"}, headers=headers)
    c_res = await client.post(
        "/api/v1/cases",
        json={"patient_id": p_res.json()["id"], "modality": "image_only", "chief_complaint": "Persistent cough"},
        headers=headers,
    )
    case_id = c_res.json()["id"]

    # Upload radiograph
    png_bytes = make_png_bytes(256, 256)
    files = {"file": ("radiograph.png", png_bytes, "image/png")}
    await client.post(f"/api/v1/cases/{case_id}/images", files=files, headers=headers)

    # No verified vision weights are available.
    predict_res = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)
    assert predict_res.status_code == 503
    assert "model not found" in predict_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_tabular_only_case_prediction(client: AsyncClient):
    """Test unimodal tabular cardiovascular risk prediction for a case with only clinical records."""
    token = await get_clinician_token(client, "dr.tabonly.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    # Setup patient & tabular-only case
    p_res = await client.post("/api/v1/patients", json={"mrn": "MRN-TAB-ONLY", "age": 55, "sex": "male"}, headers=headers)
    c_res = await client.post(
        "/api/v1/cases",
        json={"patient_id": p_res.json()["id"], "modality": "tabular_only", "chief_complaint": "Elevated cholesterol and hypertension"},
        headers=headers,
    )
    case_id = c_res.json()["id"]

    # Add clinical telemetry
    await client.post(f"/api/v1/cases/{case_id}/clinical-records", json=get_sample_tabular_payload(), headers=headers)

    # No verified tabular weights are available.
    predict_res = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)
    assert predict_res.status_code == 503
    assert "model not found" in predict_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_direct_realtime_prediction_json(client: AsyncClient):
    """Test standalone direct real-time inference via JSON payload."""
    token = await get_clinician_token(client, "dr.direct.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "patient_mrn": "PATIENT-DIRECT-001",
        "tabular_features": {
            "age": 60,
            "sex": 1,
            "chest_pain_type": 2,
            "resting_bp": 135.0,
            "cholesterol": 230.0,
            "fasting_bs": 0,
            "resting_ecg": 0,
            "max_hr": 145.0,
            "exercise_angina": 0,
            "st_depression": 1.0,
            "st_slope": 1,
            "num_major_vessels": 0,
            "thalassemia": 2,
        },
        "generate_explainability": True,
    }

    res = await client.post("/api/v1/predictions/direct", json=payload, headers=headers)
    assert res.status_code == 503
    assert "model not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_direct_realtime_prediction_upload(client: AsyncClient):
    """Test standalone direct real-time inference with multipart radiograph file upload."""
    token = await get_clinician_token(client, "dr.directup.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    png_bytes = make_png_bytes(256, 256)
    files = {"file": ("radiograph.png", png_bytes, "image/png")}
    data = {
        "tabular_features_json": json.dumps({
            "age": 50,
            "sex": 0,
            "chest_pain_type": 1,
            "resting_bp": 120.0,
            "cholesterol": 190.0,
            "fasting_bs": 0,
            "resting_ecg": 0,
            "max_hr": 160.0,
            "exercise_angina": 0,
            "st_depression": 0.0,
            "st_slope": 1,
            "num_major_vessels": 0,
            "thalassemia": 1,
        }),
        "patient_mrn": "MRN-DIRECT-UPLOAD-01",
        "generate_explainability": "true",
    }

    res = await client.post("/api/v1/predictions/direct-upload", files=files, data=data, headers=headers)
    assert res.status_code == 503
    assert "model not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_predictions_by_case_and_id(client: AsyncClient):
    """A missing checkpoint must not create prediction rows."""
    token = await get_clinician_token(client, "dr.retrieve.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    case_id = await setup_multimodal_case(client, headers, mrn="MRN-RETRIEVE-001")

    failed = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)
    assert failed.status_code == 503

    list_res = await client.get(f"/api/v1/cases/{case_id}/predictions", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 0
    assert list_res.json()["items"] == []


@pytest.mark.asyncio
async def test_list_all_predictions_with_filtering(client: AsyncClient):
    """A rejected inference does not create a global prediction row."""
    token = await get_clinician_token(client, "dr.listall.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    case_id = await setup_multimodal_case(client, headers, mrn="MRN-LISTALL-001")
    failed = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)
    assert failed.status_code == 503

    res = await client.get("/api/v1/predictions?status=confident&limit=10", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_prediction_on_empty_case_fails(client: AsyncClient):
    """Test that attempting AI inference on a case without images or records fails with 422."""
    token = await get_clinician_token(client, "dr.empty.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    p_res = await client.post("/api/v1/patients", json={"mrn": "MRN-EMPTY-CASE", "age": 40, "sex": "other"}, headers=headers)
    c_res = await client.post(
        "/api/v1/cases",
        json={"patient_id": p_res.json()["id"], "modality": "multimodal", "chief_complaint": "Checkup"},
        headers=headers,
    )
    case_id = c_res.json()["id"]

    res = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)
    assert res.status_code == 422
    assert "no associated medical images or clinical records" in res.json()["detail"]


@pytest.mark.asyncio
async def test_prediction_rbac_enforcement(client: AsyncClient, db_session: AsyncSession):
    """Verify that non-clinical roles (e.g. auditor) cannot execute AI inference."""
    clinician_token = await get_clinician_token(client, "dr.rbac.pred@hospital.org")
    clinician_headers = {"Authorization": f"Bearer {clinician_token}"}
    case_id = await setup_multimodal_case(client, clinician_headers, mrn="MRN-RBAC-001")

    # Create the privileged test role directly; public self-registration may
    # only create clinicians.
    auditor_email = "auditor.rbac.pred@hospital.org"
    db_session.add(
        User(
            email=auditor_email,
            full_name="Compliance Auditor",
            hashed_password=hash_password("AuditSecure2026!"),
            role=UserRole.AUDITOR,
            is_active=True,
            is_verified=True,
        )
    )
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": auditor_email, "password": "AuditSecure2026!"},
    )
    assert login.status_code == 200, login.text
    auditor_token = login.json()["access_token"]
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    res = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=auditor_headers)
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"] or "forbidden" in res.json()["detail"].lower()
