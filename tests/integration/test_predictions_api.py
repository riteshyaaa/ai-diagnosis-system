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
            "role": "clinician",
            "department": "Cardiology",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "DocSecure2026!"},
    )
    return login_res.json()["access_token"]


async def get_auditor_token(client: AsyncClient, email: str = "auditor.pred@hospital.org") -> str:
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

    # Execute Prediction
    predict_res = await client.post(
        f"/api/v1/cases/{case_id}/predict",
        json={"generate_explainability": True},
        headers=headers,
    )
    assert predict_res.status_code == 201
    pred = predict_res.json()

    # Verify Core Prediction Metadata
    assert pred["id"] is not None
    assert pred["case_id"] == case_id
    assert pred["model_type"] == "multimodal_fusion"
    assert pred["model_version"] == "1.0.0"
    assert pred["inference_latency_ms"] > 0
    assert 0.0 <= pred["raw_probability"] <= 1.0
    assert 0.0 <= pred["calibrated_probability"] <= 1.0

    # Verify Pathology Findings (5-label multi-label chest X-ray)
    assert len(pred["pathology_findings"]) == 5
    pathologies = {f["pathology"]: f for f in pred["pathology_findings"]}
    assert "Atelectasis" in pathologies
    assert "Cardiomegaly" in pathologies
    assert "Effusion" in pathologies
    assert "Infiltration" in pathologies
    assert "Mass" in pathologies

    # Verify Tabular Cardiovascular Risk
    assert pred["clinical_risk"] is not None
    assert 0.0 <= pred["clinical_risk"]["calibrated_probability"] <= 1.0
    assert pred["clinical_risk"]["risk_tier"] in ["low", "moderate", "high", "critical"]

    # Verify Modality Gating Weights
    assert pred["modality_gating"] is not None
    assert 0.0 <= pred["modality_gating"]["image_weight"] <= 1.0
    assert 0.0 <= pred["modality_gating"]["tabular_weight"] <= 1.0
    dom = pred["modality_gating"]["dominant_modality"].lower()
    assert any(w in dom for w in ["radiograph", "visual", "image", "clinical", "tabular", "ehr", "balanced"])

    # Verify Uncertainty Metrics
    assert pred["uncertainty"] is not None
    assert 0.0 <= pred["uncertainty"]["confidence_score"] <= 1.0
    assert pred["uncertainty"]["confidence_band"] in ["high", "moderate", "low", "abstain"]

    # Verify Explainability Artifacts (Grad-CAM + SHAP)
    assert pred["explanation"] is not None
    assert pred["explanation"]["explanation_type"] == "multimodal_attribution"
    assert pred["explanation"]["overlay_base64"] is not None
    assert pred["explanation"]["heatmap_path"] is not None
    assert pred["explanation"]["shap_values"] is not None
    assert len(pred["explanation"]["top_features"]) > 0
    assert "MultimodalLateFusion evaluated" in pred["explanation"]["summary_text"]

    # Verify Mandatory Clinical CDSS Regulatory Disclaimer
    assert "MedFusion AI is an assistive Clinical Decision Support System" in pred["clinical_disclaimer"]
    assert "does not provide autonomous medical diagnosis" in pred["clinical_disclaimer"]

    # Verify Case Status transitioned to COMPLETED
    case_res = await client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert case_res.status_code == 200
    assert case_res.json()["status"] == "completed"


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

    # Predict
    predict_res = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)
    assert predict_res.status_code == 201
    pred = predict_res.json()

    assert pred["model_type"] == "vision_classifier"
    assert len(pred["pathology_findings"]) == 5
    assert pred["clinical_risk"] is None
    assert pred["modality_gating"] is None
    assert pred["explanation"]["explanation_type"] == "gradcam_saliency"
    assert pred["explanation"]["overlay_base64"] is not None


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

    # Predict
    predict_res = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)
    assert predict_res.status_code == 201
    pred = predict_res.json()

    assert pred["model_type"] == "tabular_mlp"
    assert len(pred["pathology_findings"]) == 0
    assert pred["clinical_risk"] is not None
    assert pred["explanation"]["explanation_type"] == "shap_feature_importance"
    assert pred["explanation"]["shap_values"] is not None


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
    assert res.status_code == 200
    pred = res.json()

    assert pred["case_id"] is None
    assert pred["model_type"] == "tabular_mlp"
    assert pred["clinical_risk"] is not None
    assert pred["uncertainty"] is not None
    assert "assistive Clinical Decision Support System" in pred["clinical_disclaimer"]


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
    assert res.status_code == 200
    pred = res.json()

    assert pred["case_id"] is None
    assert pred["model_type"] == "multimodal_fusion"
    assert len(pred["pathology_findings"]) == 5
    assert pred["clinical_risk"] is not None
    assert pred["modality_gating"] is not None
    assert pred["explanation"]["overlay_base64"] is not None


@pytest.mark.asyncio
async def test_get_predictions_by_case_and_id(client: AsyncClient):
    """Test retrieving predictions by case ID, latest prediction, and specific prediction UUID."""
    token = await get_clinician_token(client, "dr.retrieve.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    case_id = await setup_multimodal_case(client, headers, mrn="MRN-RETRIEVE-001")

    # Run inference twice to create history
    res1 = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)
    assert res1.status_code == 201
    pred1_id = res1.json()["id"]

    res2 = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)
    assert res2.status_code == 201
    pred2_id = res2.json()["id"]

    # 1. Get all predictions for case
    list_res = await client.get(f"/api/v1/cases/{case_id}/predictions", headers=headers)
    assert list_res.status_code == 200
    case_preds = list_res.json()
    assert case_preds["total"] >= 2
    pred_ids = [p["id"] for p in case_preds["items"]]
    assert pred1_id in pred_ids
    assert pred2_id in pred_ids

    # 2. Get latest prediction for case
    latest_res = await client.get(f"/api/v1/cases/{case_id}/predictions/latest", headers=headers)
    assert latest_res.status_code == 200
    assert latest_res.json()["id"] == pred2_id

    # 3. Get specific prediction by ID
    single_res = await client.get(f"/api/v1/predictions/{pred1_id}", headers=headers)
    assert single_res.status_code == 200
    assert single_res.json()["id"] == pred1_id


@pytest.mark.asyncio
async def test_list_all_predictions_with_filtering(client: AsyncClient):
    """Test querying and paginating all predictions with status filtering."""
    token = await get_clinician_token(client, "dr.listall.pred@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    case_id = await setup_multimodal_case(client, headers, mrn="MRN-LISTALL-001")
    await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=headers)

    res = await client.get("/api/v1/predictions?status=confident&limit=10", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert isinstance(data["items"], list)
    for p in data["items"]:
        assert p["status"] == "confident"


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
async def test_prediction_rbac_enforcement(client: AsyncClient):
    """Verify that non-clinical roles (e.g. auditor) cannot execute AI inference."""
    clinician_token = await get_clinician_token(client, "dr.rbac.pred@hospital.org")
    clinician_headers = {"Authorization": f"Bearer {clinician_token}"}
    case_id = await setup_multimodal_case(client, clinician_headers, mrn="MRN-RBAC-001")

    # Auditor attempting prediction
    auditor_token = await get_auditor_token(client, "auditor.rbac.pred@hospital.org")
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    res = await client.post(f"/api/v1/cases/{case_id}/predict", json={}, headers=auditor_headers)
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"] or "forbidden" in res.json()["detail"].lower()
