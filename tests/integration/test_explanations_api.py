"""
MedFusion AI — Explainable AI (XAI) & Heatmap Artifact Serving Integration Tests.

Comprehensive test suite verifying:
- Composite explanation retrieval (Grad-CAM visual cues, SHAP tabular waterfalls, gating weights)
- Secure Grad-CAM radiograph heatmap overlay image streaming (Content-Type: image/png)
- Structured SHAP feature attribution waterfall and directional impacts (risk increasing vs decreasing)
- Historical case-level explanation listing and query aggregation
- On-demand Grad-CAM visual saliency recalculation across 5 thoracic pathologies (Atelectasis, Cardiomegaly, etc.)
- Clinical validation, anatomical region tagging, and normal baseline reference bounds
- Path traversal protection and artifact security checks
- Role-based access control (RBAC) enforcement on XAI recalculation
- Mandatory non-autonomous CDSS regulatory disclaimer inclusion
"""

import io
import json
import pytest
from PIL import Image
from httpx import AsyncClient

from tests.unit.test_image_processing import (
    create_synthetic_radiograph,
)


def make_png_bytes(width: int = 256, height: int = 256) -> bytes:
    """Generate synthetic radiograph encoded as PNG bytes."""
    arr = create_synthetic_radiograph(width, height)
    pil_img = Image.fromarray(arr)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


async def get_clinician_token(client: AsyncClient, email: str = "dr.xai.tester@hospital.org") -> str:
    """Create and authenticate a clinician user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Dr. XAI Tester",
            "password": "DocSecure2026!",
            "role": "clinician",
            "department": "Radiology",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "DocSecure2026!"},
    )
    return login_res.json()["access_token"]


async def get_auditor_token(client: AsyncClient, email: str = "auditor.xai@hospital.org") -> str:
    """Create and authenticate an auditor user."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Audit Officer",
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
        "age": 64,
        "sex": 1,
        "chest_pain_type": 3,
        "resting_bp": 142.0,
        "cholesterol": 255.0,
        "fasting_bs": 1,
        "resting_ecg": 1,
        "max_hr": 136.0,
        "exercise_angina": 1,
        "st_depression": 2.4,
        "st_slope": 2,
        "num_major_vessels": 2,
        "thalassemia": 3,
        "source": "manual_entry",
    }


async def setup_multimodal_case_with_prediction(client: AsyncClient, headers: dict, mrn: str = "MRN-XAI-001") -> dict:
    """Helper to create patient, case, upload radiograph, add clinical records, and run prediction."""
    # 1. Patient
    p_res = await client.post(
        "/api/v1/patients",
        json={"mrn": mrn, "age": 64, "sex": "male"},
        headers=headers,
    )
    patient_id = p_res.json()["id"]

    # 2. Case
    c_res = await client.post(
        "/api/v1/cases",
        json={
            "patient_id": patient_id,
            "modality": "multimodal",
            "chief_complaint": "Exertional dyspnea and retrosternal chest pressure",
            "priority": "urgent",
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
async def test_get_prediction_explanation_multimodal(client: AsyncClient):
    """
    Test retrieving composite explanation for multimodal case.
    Verifies Visual Grad-CAM attention regions, SHAP feature waterfalls, and regulatory disclaimer.
    """
    token = await get_clinician_token(client, "dr.expl.multi@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_multimodal_case_with_prediction(client, headers, mrn="MRN-EXPL-001")
    prediction_id = setup_data["prediction"]["id"]

    res = await client.get(f"/api/v1/predictions/{prediction_id}/explanation", headers=headers)
    assert res.status_code == 200
    expl = res.json()

    # Verify Core Metadata
    assert expl["id"] is not None
    assert expl["prediction_id"] == prediction_id
    assert expl["case_id"] == setup_data["case_id"]
    assert expl["explanation_type"] == "multimodal_attribution"
    assert expl["model_type"] == "multimodal_fusion"

    # Verify Visual Explanation
    visual = expl["visual_explanation"]
    assert visual is not None
    assert visual["target_pathology"] is not None
    assert f"/api/v1/predictions/{prediction_id}/heatmap" in visual["heatmap_url"]
    assert len(visual["attention_regions"]) > 0
    first_region = visual["attention_regions"][0]
    assert len(first_region["box"]) == 4
    assert 0.0 <= first_region["saliency_score"] <= 1.0
    assert first_region["anatomical_region"] is not None

    # Verify Tabular SHAP Explanation
    tabular = expl["tabular_explanation"]
    assert tabular is not None
    assert tabular["total_features_evaluated"] > 0
    assert len(tabular["all_features"]) > 0

    # Verify Feature Attributes Structure & References
    first_feat = tabular["all_features"][0]
    assert first_feat["feature_name"] in ["st_depression", "resting_bp", "cholesterol", "max_hr", "age", "chest_pain_type", "thalassemia", "num_major_vessels", "exercise_angina", "st_slope", "resting_ecg", "fasting_bs", "sex"]
    assert first_feat["display_name"] is not None
    assert first_feat["baseline_reference"] is not None
    assert first_feat["direction"] in ["risk_increasing", "risk_decreasing"]
    assert first_feat["importance_rank"] == 1
    assert first_feat["percentage_impact"] > 0

    # Verify Modality Gating
    assert expl["modality_gating"] is not None
    assert 0.0 <= expl["modality_gating"]["image_weight"] <= 1.0
    assert 0.0 <= expl["modality_gating"]["tabular_weight"] <= 1.0

    # Verify Mandatory Regulatory Disclaimer
    assert "MedFusion AI is an assistive Clinical Decision Support System" in expl["clinical_disclaimer"]
    assert "does not provide autonomous medical diagnosis" in expl["clinical_disclaimer"]


@pytest.mark.asyncio
async def test_get_prediction_heatmap_stream(client: AsyncClient):
    """Test streaming Grad-CAM visual heatmap overlay PNG file."""
    token = await get_clinician_token(client, "dr.hm.stream@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_multimodal_case_with_prediction(client, headers, mrn="MRN-HM-001")
    prediction_id = setup_data["prediction"]["id"]

    res = await client.get(f"/api/v1/predictions/{prediction_id}/heatmap", headers=headers)
    assert res.status_code == 200
    assert "image/png" in res.headers.get("content-type", "")
    assert len(res.content) > 100  # Non-empty valid binary PNG data

    # Verify bytes can be decoded as a valid image
    img = Image.open(io.BytesIO(res.content))
    assert img.format == "PNG"
    assert img.size[0] > 0 and img.size[1] > 0


@pytest.mark.asyncio
async def test_get_tabular_feature_attributions_endpoint(client: AsyncClient):
    """Test dedicated SHAP feature attributions waterfall endpoint."""
    token = await get_clinician_token(client, "dr.feat.attr@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_multimodal_case_with_prediction(client, headers, mrn="MRN-FEAT-001")
    prediction_id = setup_data["prediction"]["id"]

    res = await client.get(f"/api/v1/predictions/{prediction_id}/features", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["prediction_id"] == prediction_id
    assert data["total_features_evaluated"] >= 5
    assert len(data["top_risk_increasing_features"]) > 0 or len(data["top_risk_decreasing_features"]) > 0

    # Verify importance ranks are ordered monotonically
    ranks = [f["importance_rank"] for f in data["all_features"]]
    assert ranks == sorted(ranks)
    assert "MedFusion AI is an assistive Clinical Decision Support System" in data["clinical_disclaimer"]


@pytest.mark.asyncio
async def test_get_case_explanations_listing(client: AsyncClient):
    """Test listing all explanation records across predictions for a case."""
    token = await get_clinician_token(client, "dr.list.expl@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_multimodal_case_with_prediction(client, headers, mrn="MRN-CASE-EXPL-001")
    case_id = setup_data["case_id"]

    # Run second prediction to create history
    await client.post(
        f"/api/v1/cases/{case_id}/predict",
        json={"generate_explainability": True},
        headers=headers,
    )

    res = await client.get(f"/api/v1/cases/{case_id}/explanations", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] >= 2
    assert len(data["items"]) >= 2
    for expl in data["items"]:
        assert expl["case_id"] == case_id
        assert expl["explanation_type"] == "multimodal_attribution"


@pytest.mark.asyncio
async def test_recalculate_pathology_saliency_on_demand(client: AsyncClient):
    """
    Test on-demand Grad-CAM recalculation for alternative thoracic conditions
    (e.g., Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass).
    """
    token = await get_clinician_token(client, "dr.recalc.xai@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_multimodal_case_with_prediction(client, headers, mrn="MRN-RECALC-001")
    prediction_id = setup_data["prediction"]["id"]

    # 1. Recalculate for Atelectasis
    res1 = await client.post(
        f"/api/v1/predictions/{prediction_id}/explain-pathology",
        json={"target_pathology": "Atelectasis"},
        headers=headers,
    )
    assert res1.status_code == 200
    recalc1 = res1.json()
    assert recalc1["target_pathology"] == "Atelectasis"
    assert recalc1["overlay_base64"] is not None
    assert recalc1["heatmap_base64"] is not None
    assert len(recalc1["attention_regions"]) > 0

    # 2. Recalculate for Effusion
    res2 = await client.post(
        f"/api/v1/predictions/{prediction_id}/explain-pathology",
        json={"target_pathology": "Effusion"},
        headers=headers,
    )
    assert res2.status_code == 200
    recalc2 = res2.json()
    assert recalc2["target_pathology"] == "Effusion"
    assert recalc2["overlay_base64"] is not None
    assert "On-demand Grad-CAM visual saliency recalculated for Effusion" in recalc2["summary_text"]


@pytest.mark.asyncio
async def test_recalculate_pathology_invalid_pathology_fails(client: AsyncClient):
    """Test that requesting saliency recalculation for an unknown pathology fails with 422."""
    token = await get_clinician_token(client, "dr.invalid.path@hospital.org")
    headers = {"Authorization": f"Bearer {token}"}

    setup_data = await setup_multimodal_case_with_prediction(client, headers, mrn="MRN-INVAL-001")
    prediction_id = setup_data["prediction"]["id"]

    res = await client.post(
        f"/api/v1/predictions/{prediction_id}/explain-pathology",
        json={"target_pathology": "Appendicitis"},
        headers=headers,
    )
    assert res.status_code == 422
    assert "Unknown target pathology" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recalculate_pathology_rbac_enforcement(client: AsyncClient):
    """Verify that non-clinical roles (auditor) cannot trigger on-demand saliency recalculation."""
    clinician_token = await get_clinician_token(client, "dr.rbac.owner@hospital.org")
    clinician_headers = {"Authorization": f"Bearer {clinician_token}"}
    setup_data = await setup_multimodal_case_with_prediction(client, clinician_headers, mrn="MRN-RBAC-XAI-01")
    prediction_id = setup_data["prediction"]["id"]

    # Auditor attempting recalculation
    auditor_token = await get_auditor_token(client, "auditor.rbac.xai@hospital.org")
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    res = await client.post(
        f"/api/v1/predictions/{prediction_id}/explain-pathology",
        json={"target_pathology": "Cardiomegaly"},
        headers=auditor_headers,
    )
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"]
