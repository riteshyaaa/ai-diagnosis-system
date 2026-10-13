"""End-to-end smoke test for the supported upload path and missing-model behavior."""

import io
import pytest
from PIL import Image
from httpx import AsyncClient

from tests.unit.test_image_processing import (
    create_synthetic_radiograph,
)


def generate_test_radiograph_bytes(width: int = 256, height: int = 256) -> bytes:
    """Generate synthetic radiograph image as PNG byte stream."""
    arr = create_synthetic_radiograph(width, height)
    pil_img = Image.fromarray(arr)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_case_upload_workflow_fails_closed_without_model_artifacts(client: AsyncClient):
    """Verify authenticated intake works, while unavailable weights block inference."""
    # -------------------------------------------------------------------------
    # 1. Clinician Registration & Authentication
    # -------------------------------------------------------------------------
    clinician_email = "dr.sarah.connor@university-hospital.edu"
    clinician_password = "MedSecure2026!Clinical"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": clinician_email,
            "full_name": "Dr. Sarah Connor, MD",
            "password": clinician_password,
            "department": "Cardiothoracic Medicine",
        },
    )
    assert reg_res.status_code == 201
    clinician_user = reg_res.json()
    assert clinician_user["role"] == "clinician"

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": clinician_email, "password": clinician_password},
    )
    assert login_res.status_code == 200
    clinician_token = login_res.json()["access_token"]
    clinician_headers = {"Authorization": f"Bearer {clinician_token}"}

    # -------------------------------------------------------------------------
    # 2. Patient Intake & HIPAA SHA-256 Salted Hashing Verification
    # -------------------------------------------------------------------------
    raw_mrn = "MRN-E2E-984214-CARDIAC"
    patient_res = await client.post(
        "/api/v1/patients",
        json={
            "mrn": raw_mrn,
            "age": 58,
            "sex": "male",
            "medical_history_summary": "58yo male with exertional dyspnea, orthopnea, and suspected cardiomegaly.",
        },
        headers=clinician_headers,
    )
    assert patient_res.status_code == 201
    patient = patient_res.json()
    assert patient["id"] is not None
    assert patient["age"] == 58
    assert patient["sex"] == "male"
    assert "mrn_hash" in patient
    assert len(patient["mrn_hash"]) == 64  # Hex-encoded SHA-256 hash digest

    # -------------------------------------------------------------------------
    # 3. Diagnostic Case Creation
    # -------------------------------------------------------------------------
    case_res = await client.post(
        "/api/v1/cases",
        json={
            "patient_id": patient["id"],
            "modality": "multimodal",
            "chief_complaint": "Acute Progressive Dyspnea & Retrosternal Chest Pressure",
            "clinical_notes": "Presenting with 3-day history of worsening exertional dyspnea, orthopnea, and bilateral lower extremity edema.",
            "priority": "urgent",
        },
        headers=clinician_headers,
    )
    assert case_res.status_code == 201
    case = case_res.json()
    case_id = case["id"]
    assert case["status"] == "draft"
    assert case["modality"] == "multimodal"

    # -------------------------------------------------------------------------
    # 4. Multimodal Data Ingestion: Chest Radiograph Image & DICOM
    # -------------------------------------------------------------------------
    cxr_bytes = generate_test_radiograph_bytes(256, 256)
    img_upload_res = await client.post(
        f"/api/v1/cases/{case_id}/images",
        files={"file": ("chest_xray_pa.png", cxr_bytes, "image/png")},
        data={"image_type": "chest_xray_pa"},
        headers=clinician_headers,
    )
    assert img_upload_res.status_code == 201
    image_record = img_upload_res.json()["image"]
    assert image_record["image_type"] == "chest_xray_pa"
    assert image_record["file_hash"] is not None
    assert len(image_record["file_hash"]) == 64

    # -------------------------------------------------------------------------
    # 5. Multimodal Data Ingestion: 13-Parameter Clinical Telemetry
    # -------------------------------------------------------------------------
    telemetry_payload = {
        "age": 58,
        "sex": 1,
        "chest_pain_type": 3,
        "resting_bp": 142.0,
        "cholesterol": 268.0,
        "fasting_bs": 1,
        "resting_ecg": 1,
        "max_hr": 134.0,
        "exercise_angina": 1,
        "st_depression": 2.4,
        "st_slope": 2,
        "num_major_vessels": 2,
        "thalassemia": 3,
        "source": "icu_telemetry_intake",
    }
    telemetry_res = await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=telemetry_payload,
        headers=clinician_headers,
    )
    assert telemetry_res.status_code == 201
    clinical_record = telemetry_res.json()["record"]
    assert clinical_record["resting_bp"] == 142.0
    assert clinical_record["cholesterol"] == 268.0

    predict_res = await client.post(
        f"/api/v1/cases/{case_id}/predict",
        json={
            "generate_explainability": True,
        },
        headers=clinician_headers,
    )
    assert predict_res.status_code == 503
    assert "model not found" in predict_res.json()["detail"].lower()

    # A failed inference cannot produce or persist a clinical-looking response.
    case_detail_res = await client.get(f"/api/v1/cases/{case_id}", headers=clinician_headers)
    assert case_detail_res.status_code == 200
    case_detail = case_detail_res.json()
    assert case_detail["status"] == "draft"
    predictions_res = await client.get(
        f"/api/v1/cases/{case_id}/predictions",
        headers=clinician_headers,
    )
    assert predictions_res.status_code == 200
    assert predictions_res.json()["total"] == 0
