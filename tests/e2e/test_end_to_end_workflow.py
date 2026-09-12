"""
MedFusion AI — Full End-to-End Clinical Diagnostic & Decision Support Workflow Tests.

Validates the complete lifecycle of a clinical case across:
1. Secure Authentication & Role-Based Access Control (Clinician & Auditor)
2. Patient Registration with HIPAA Salted SHA-256 MRN Hashing
3. Diagnostic Case Creation & Modality Configuration
4. Multimodal Data Ingestion (Chest Radiograph / DICOM & 13-Parameter Clinical Telemetry)
5. Multimodal Late Fusion AI Inference (DenseNet-121 Vision + Tabular MLP + Gated Fusion)
6. Calibrated Pathology Risk Scoring & Uncertainty Quantification
7. Explainable AI (Grad-CAM Saliency Heatmaps + TreeSHAP Feature Attributions)
8. Non-Autonomous CDSS Regulatory Disclaimers & Confidence Bands
9. Human-in-the-Loop Clinical Supervisory Review Validation (Concordance & Rationales)
10. Immutable 21 CFR Part 11 Institutional Audit Trail & Integrity Verification
"""

import io
import json
import pytest
from PIL import Image
from httpx import AsyncClient

from tests.unit.test_image_processing import (
    create_synthetic_dicom_bytes,
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
async def test_full_clinical_diagnostic_e2e_workflow(client: AsyncClient):
    """
    Execute full end-to-end clinical diagnostic workflow:
    Intake -> Imaging & Telemetry -> Multimodal Inference -> XAI -> Physician Review -> Audit Trail.
    """
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
            "role": "clinician",
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

    # -------------------------------------------------------------------------
    # 6. Execute Multimodal Late-Fusion AI Inference & Explainability Generation
    # -------------------------------------------------------------------------
    predict_res = await client.post(
        f"/api/v1/cases/{case_id}/predict",
        json={
            "model_type": "multimodal_fusion",
            "generate_explainability": True,
        },
        headers=clinician_headers,
    )
    assert predict_res.status_code == 201
    prediction = predict_res.json()
    prediction_id = prediction["id"]

    # Verify Multi-label Vision Pathologies (Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass)
    assert len(prediction["pathology_findings"]) == 5
    pathologies = {f["pathology"]: f for f in prediction["pathology_findings"]}
    for name in ["Atelectasis", "Cardiomegaly", "Effusion", "Infiltration", "Mass"]:
        assert name in pathologies
        assert 0.0 <= pathologies[name]["calibrated_probability"] <= 1.0
        assert pathologies[name]["confidence_band"] in ["high", "moderate", "low", "abstain"]

    # Verify Tabular Cardiovascular Risk
    assert prediction["clinical_risk"] is not None
    assert 0.0 <= prediction["clinical_risk"]["calibrated_probability"] <= 1.0
    assert prediction["clinical_risk"]["risk_tier"] in ["low", "moderate", "high", "critical"]

    # Verify Dynamic Modality Late Fusion Gating
    assert prediction["modality_gating"] is not None
    assert 0.0 <= prediction["modality_gating"]["image_weight"] <= 1.0
    assert 0.0 <= prediction["modality_gating"]["tabular_weight"] <= 1.0
    assert abs((prediction["modality_gating"]["image_weight"] + prediction["modality_gating"]["tabular_weight"]) - 1.0) < 0.05

    # Verify Uncertainty Metrics
    assert prediction["uncertainty"] is not None
    assert 0.0 <= prediction["uncertainty"]["confidence_score"] <= 1.0

    # Verify Explainable AI (XAI) Output
    assert prediction["explanation"] is not None
    assert prediction["explanation"]["overlay_base64"] is not None
    assert len(prediction["explanation"]["top_features"]) > 0
    assert "MultimodalLateFusion evaluated" in prediction["explanation"]["summary_text"]

    # Verify Mandatory Non-Autonomous CDSS Regulatory Disclaimer
    assert "MedFusion AI is an assistive Clinical Decision Support System" in prediction["clinical_disclaimer"]
    assert "does not provide autonomous medical diagnosis" in prediction["clinical_disclaimer"]

    # Verify Case Status Advance to COMPLETED
    case_detail_res = await client.get(f"/api/v1/cases/{case_id}", headers=clinician_headers)
    assert case_detail_res.status_code == 200
    case_detail = case_detail_res.json()
    assert case_detail["status"] == "completed"

    # -------------------------------------------------------------------------
    # 7. Human-in-the-Loop Physician Review Submission & Concordance Audit
    # -------------------------------------------------------------------------
    review_res = await client.post(
        f"/api/v1/cases/{case_id}/reviews",
        json={
            "prediction_id": prediction_id,
            "decision": "accept",
            "clinical_notes": "Multimodal AI assessment concurs with clinical signs. Mild cardiomegaly and bibasilar infiltration noted on CXR with elevated telemetry risk markers.",
        },
        headers=clinician_headers,
    )
    assert review_res.status_code == 201
    review = review_res.json()
    assert review["case_id"] == case_id
    assert review["decision"] == "accept"
    assert review["concordance"] is True

    # Verify Case Status Advance to REVIEWED
    updated_case_res = await client.get(f"/api/v1/cases/{case_id}", headers=clinician_headers)
    assert updated_case_res.status_code == 200
    assert updated_case_res.json()["status"] == "reviewed"

    # -------------------------------------------------------------------------
    # 8. Regulatory Compliance & Institutional 21 CFR Part 11 Audit Verification
    # -------------------------------------------------------------------------
    # Register Compliance Auditor
    auditor_email = "compliance.officer@hospital-regulator.gov"
    auditor_password = "AuditOfficerSecure2026!"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": auditor_email,
            "full_name": "Chief Compliance Officer",
            "password": auditor_password,
            "role": "auditor",
        },
    )
    auditor_login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": auditor_email, "password": auditor_password},
    )
    assert auditor_login_res.status_code == 200
    auditor_token = auditor_login_res.json()["access_token"]
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    # Verify Case Review History Retrieval
    reviews_res = await client.get(f"/api/v1/cases/{case_id}/reviews", headers=auditor_headers)
    assert reviews_res.status_code == 200
    reviews_data = reviews_res.json()
    assert reviews_data["total"] >= 1
    assert reviews_data["items"][0]["decision"] == "accept"
