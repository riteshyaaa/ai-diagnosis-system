"""
Unit Tests for MedFusion AI Model Registry & Unified Inference Service.

Covers:
- Model Registry registration, manifest management, and cryptographic SHA-256 verification
- Tamper detection via SHA-256 checksum validation
- Model loading across Vision, Tabular MLP, and Multimodal Late Fusion architectures
- Patient privacy protection (SHA-256 MRN hashing)
- Unimodal Image-only clinical inference & Grad-CAM visual artifacts
- Unimodal Tabular-only clinical risk prediction & SHAP feature attributions
- Multimodal Late Fusion inference with dynamic modality gating weights
- Clinical uncertainty quantification, entropy estimation, and safety abstention rules
- Input validation and error handling for corrupt/missing modalities
- Mandatory non-autonomous CDSS regulatory disclaimer inclusion
"""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch
from PIL import Image

from ml.inference.schemas import (
    ConfidenceBand,
    InferenceModality,
    InferenceRequest,
    InferenceResponse,
    RiskTier,
)
from ml.inference.service import UnifiedInferenceService
from ml.models.image.classifier import ChestXRayClassifier
from ml.models.tabular.neural_models import TabularRiskMLP
from ml.registry.registry import ModelMetadata, ModelRegistry, ModelStatus, ModelType


@pytest.fixture
def temp_registry_dir():
    """Create a clean temporary directory for model registry testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_synthetic_xray_array():
    """Generate a clean synthetic 224x224 RGB radiograph."""
    np.random.seed(42)
    # Realistic chest X-ray synthetic ground: dark background with bright lung/heart central shapes
    img = np.zeros((224, 224, 3), dtype=np.uint8) + 40
    # Simulate central mediastinum / heart opacity
    img[60:180, 80:150] = 160
    # Simulate lung fields
    img[50:160, 30:75] = 90
    img[50:160, 155:200] = 90
    # Add subtle anatomical noise
    noise = np.random.randint(-15, 15, (224, 224, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return img


@pytest.fixture
def sample_valid_tabular_dict():
    """Generate standard valid clinical patient telemetry."""
    return {
        "age": 62,
        "sex": 1,
        "chest_pain_type": 3,
        "resting_bp": 138.0,
        "cholesterol": 245.0,
        "fasting_bs": 0,
        "resting_ecg": 1,
        "max_hr": 142.0,
        "exercise_angina": 1,
        "st_depression": 1.8,
        "st_slope": 2,
        "num_major_vessels": 1,
        "thalassemia": 2,
    }


# =========================================================================
# Model Registry Tests
# =========================================================================


def test_registry_initialization_and_manifest(temp_registry_dir):
    """Test registry directory creation and manifest initialization."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    assert registry.manifest_file.exists()

    manifest = registry._read_manifest()
    assert manifest["registry_version"] == "1.0.0"
    assert "models" in manifest


def test_register_and_load_vision_model(temp_registry_dir):
    """Test registering a ChestXRayClassifier and loading it back with checksum verification."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    model = ChestXRayClassifier(backbone_name="densenet121", num_classes=5, embedding_dim=512, pretrained=False)

    meta = registry.register_model(
        model_name="chest_xray_vision",
        model_type=ModelType.VISION_CLASSIFIER,
        model_object=model,
        version="1.0.0",
        metrics={"macro_auroc": 0.89},
        description="Vision model test",
    )

    assert meta.model_name == "chest_xray_vision"
    assert meta.sha256_checksum != ""
    assert meta.version == "1.0.0"

    # Load back
    loaded_model, loaded_meta, aux = registry.load_model("chest_xray_vision", version="1.0.0")
    assert isinstance(loaded_model, ChestXRayClassifier)
    assert loaded_meta.metrics["macro_auroc"] == 0.89


def test_registry_tamper_detection(temp_registry_dir):
    """Test that altering a model artifact triggers a cryptographic integrity error."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    model = TabularRiskMLP(input_dim=13, embedding_dim=128, hidden_dim=128)

    meta = registry.register_model(
        model_name="tabular_risk_mlp",
        model_type=ModelType.TABULAR_MLP,
        model_object=model,
        version="1.0.0",
    )

    artifact_file = temp_registry_dir / "tabular_risk_mlp" / "v1.0.0" / meta.artifact_filename
    assert artifact_file.exists()

    # Tamper with file
    with open(artifact_file, "ab") as f:
        f.write(b"CORRUPTED_MALICIOUS_BYTES")

    # Loading with checksum verification must raise ValueError
    with pytest.raises(ValueError, match="Integrity check failed"):
        registry.load_model("tabular_risk_mlp", version="1.0.0", verify_checksum=True)


def test_registry_list_models_and_set_active(temp_registry_dir):
    """Test listing catalog models and updating active deployment versions."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    registry.ensure_default_models_registered()

    model_list = registry.list_models()
    names = [m["model_name"] for m in model_list]
    assert "chest_xray_vision" in names
    assert "tabular_risk_mlp" in names
    assert "multimodal_late_fusion" in names

    # Register v2.0.0 and promote
    tab_model = TabularRiskMLP(input_dim=13, embedding_dim=128, hidden_dim=128)
    registry.register_model(
        model_name="tabular_risk_mlp",
        model_type=ModelType.TABULAR_MLP,
        model_object=tab_model,
        version="2.0.0",
        status=ModelStatus.STAGING,
    )

    registry.set_active_version("tabular_risk_mlp", "2.0.0")
    summary = next(m for m in registry.list_models() if m["model_name"] == "tabular_risk_mlp")
    assert summary["active_version"] == "2.0.0"


# =========================================================================
# Unified Inference Service Tests
# =========================================================================


def test_inference_patient_mrn_privacy_hashing(temp_registry_dir, sample_synthetic_xray_array):
    """Verify that patient MRN is cryptographically hashed and never returned in plaintext."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    raw_mrn = "PATIENT-MRN-98765-CONFIDENTIAL"
    expected_hash = hashlib.sha256(raw_mrn.encode("utf-8")).hexdigest()

    req = InferenceRequest(
        patient_mrn=raw_mrn,
        image_bytes=cv2.imencode(".png", sample_synthetic_xray_array)[1].tobytes(),
        generate_explainability=False,
    )
    res = service.predict(req)

    assert res.patient_mrn_hash == expected_hash
    assert raw_mrn not in json.dumps(res.model_dump())


def test_image_only_inference_and_gradcam(temp_registry_dir, sample_synthetic_xray_array):
    """Test unimodal radiograph prediction with 5-pathology findings and Grad-CAM heatmap."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    img_bytes = cv2.imencode(".png", sample_synthetic_xray_array)[1].tobytes()

    req = InferenceRequest(
        image_bytes=img_bytes,
        generate_explainability=True,
    )
    res = service.predict(req)

    assert res.modality == InferenceModality.IMAGE_ONLY
    assert len(res.pathology_findings) == 5
    path_names = [f.pathology for f in res.pathology_findings]
    assert "Atelectasis" in path_names
    assert "Cardiomegaly" in path_names
    assert "Effusion" in path_names

    # Check uncertainty
    assert 0.0 <= res.uncertainty.confidence_score <= 1.0
    assert res.uncertainty.confidence_band in [
        ConfidenceBand.HIGH,
        ConfidenceBand.MODERATE,
        ConfidenceBand.LOW,
        ConfidenceBand.ABSTAIN,
    ]

    # Check Explainability
    assert res.explainability is not None
    assert res.explainability.gradcam_heatmap_base64 is not None
    assert res.explainability.gradcam_overlay_base64 is not None
    assert res.clinical_risk is None

    # Check Clinical CDSS Regulatory Disclaimer
    assert "MedFusion AI is an assistive Clinical Decision Support System" in res.clinical_disclaimer
    assert "does not provide autonomous medical diagnosis" in res.clinical_disclaimer


def test_tabular_only_inference_and_shap(temp_registry_dir, sample_valid_tabular_dict):
    """Test unimodal tabular risk assessment, calibration, and SHAP feature contributions."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    req = InferenceRequest(
        tabular_features=sample_valid_tabular_dict,
        generate_explainability=True,
    )
    res = service.predict(req)

    assert res.modality == InferenceModality.TABULAR_ONLY
    assert res.clinical_risk is not None
    assert 0.0 <= res.clinical_risk.raw_probability <= 1.0
    assert 0.0 <= res.clinical_risk.calibrated_probability <= 1.0
    assert res.clinical_risk.risk_tier in [
        RiskTier.LOW,
        RiskTier.MODERATE,
        RiskTier.HIGH,
        RiskTier.CRITICAL,
    ]

    # SHAP explanations
    assert res.explainability is not None
    assert res.explainability.shap_feature_contributions is not None
    assert len(res.explainability.shap_feature_contributions) > 0
    top_feat_names = [item["feature"] for item in res.explainability.shap_feature_contributions]
    assert any(f in top_feat_names for f in ["age", "cholesterol", "resting_bp", "st_depression"])

    assert len(res.pathology_findings) == 0


def test_multimodal_late_fusion_inference(
    temp_registry_dir,
    sample_synthetic_xray_array,
    sample_valid_tabular_dict,
):
    """Test multimodal prediction combining image and tabular data with gating weights."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    img_bytes = cv2.imencode(".png", sample_synthetic_xray_array)[1].tobytes()

    req = InferenceRequest(
        image_bytes=img_bytes,
        tabular_features=sample_valid_tabular_dict,
        generate_explainability=True,
    )
    res = service.predict(req)

    assert res.modality == InferenceModality.MULTIMODAL
    assert len(res.pathology_findings) == 5
    assert res.clinical_risk is not None
    assert res.modality_gating is not None
    assert 0.0 <= res.modality_gating.image_weight <= 1.0
    assert 0.0 <= res.modality_gating.tabular_weight <= 1.0

    # Explainability contains both Grad-CAM and SHAP
    assert res.explainability is not None
    assert res.explainability.gradcam_heatmap_base64 is not None
    assert res.explainability.shap_feature_contributions is not None


def test_clinical_safety_abstention_on_corrupted_image(temp_registry_dir):
    """Test that all-black/all-white or degraded radiographs trigger quality safety abstention."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    # Degenerate all-black image
    black_img = np.zeros((224, 224, 3), dtype=np.uint8)
    black_bytes = cv2.imencode(".png", black_img)[1].tobytes()

    req = InferenceRequest(
        image_bytes=black_bytes,
        generate_explainability=False,
    )
    res = service.predict(req)

    assert res.uncertainty.abstention_recommended is True
    assert res.uncertainty.confidence_band == ConfidenceBand.ABSTAIN
    assert any("Image quality" in reason for reason in res.uncertainty.abstention_reasons)


def test_empty_request_raises_validation_error(temp_registry_dir):
    """Test that providing neither image nor tabular features raises an informative error."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    req = InferenceRequest()
    with pytest.raises(ValueError, match="must provide either image data, tabular features, or both"):
        service.predict(req)


def test_invalid_tabular_bounds_raises_validation_error(temp_registry_dir):
    """Test that physiologically impossible tabular inputs (e.g. resting_bp = 900) fail validation."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    invalid_tabular = {
        "age": 55,
        "sex": 1,
        "chest_pain_type": 2,
        "resting_bp": 999.0,  # Biologically impossible
        "cholesterol": 200.0,
        "fasting_bs": 0,
        "resting_ecg": 0,
        "max_hr": 150.0,
        "exercise_angina": 0,
        "st_depression": 1.0,
        "st_slope": 1,
        "num_major_vessels": 0,
        "thalassemia": 1,
    }

    req = InferenceRequest(tabular_features=invalid_tabular)
    with pytest.raises(ValueError, match="Clinical tabular validation failed"):
        service.predict(req)
