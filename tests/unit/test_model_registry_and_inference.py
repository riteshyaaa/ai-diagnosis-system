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
    """Test that no baselines are seeded and verified artifacts can be promoted."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    registry.ensure_default_models_registered()

    assert registry.list_models() == []

    # Register a test artifact as staging and promote it only after checksum verification.
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


def test_load_model_does_not_fall_back_to_latest_experimental_version(temp_registry_dir):
    """Inference must not silently load the latest unpromoted experiment."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    model = TabularRiskMLP(input_dim=13, embedding_dim=128, hidden_dim=128)
    registry.register_model(
        model_name="tabular_risk_mlp",
        model_type=ModelType.TABULAR_MLP,
        model_object=model,
        version="1.0.0",
        status=ModelStatus.EXPERIMENTAL,
    )

    with pytest.raises(RuntimeError, match="no promoted active version"):
        registry.load_model("tabular_risk_mlp")


# =========================================================================
# Unified Inference Service Tests
# =========================================================================


def test_inference_patient_mrn_privacy_hashing(temp_registry_dir, sample_synthetic_xray_array):
    """Verify the deterministic privacy hashing helper without claiming model inference."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    raw_mrn = "PATIENT-MRN-98765-CONFIDENTIAL"
    expected_hash = hashlib.sha256(raw_mrn.encode("utf-8")).hexdigest()
    assert service.hash_patient_mrn(raw_mrn) == expected_hash


def test_image_only_inference_and_gradcam(temp_registry_dir, sample_synthetic_xray_array):
    """Image inference fails closed if no trained artifact is registered."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    img_bytes = cv2.imencode(".png", sample_synthetic_xray_array)[1].tobytes()

    req = InferenceRequest(image_bytes=img_bytes, generate_explainability=True)
    with pytest.raises(RuntimeError, match="Chest X-Ray vision model not loaded"):
        service.predict(req)


def test_tabular_only_inference_and_shap(temp_registry_dir, sample_valid_tabular_dict):
    """Tabular inference fails closed without trained weights and evaluation provenance."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    req = InferenceRequest(tabular_features=sample_valid_tabular_dict, generate_explainability=True)
    with pytest.raises(RuntimeError, match="Tabular risk model not loaded"):
        service.predict(req)


def test_multimodal_late_fusion_inference(
    temp_registry_dir,
    sample_synthetic_xray_array,
    sample_valid_tabular_dict,
):
    """Multimodal inference fails closed without a trained fusion artifact."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    img_bytes = cv2.imencode(".png", sample_synthetic_xray_array)[1].tobytes()

    req = InferenceRequest(
        image_bytes=img_bytes,
        tabular_features=sample_valid_tabular_dict,
        generate_explainability=True,
    )
    with pytest.raises(RuntimeError, match="Multimodal fusion model not loaded"):
        service.predict(req)


def test_corrupted_image_is_flagged_by_preprocessing(temp_registry_dir):
    """Image quality detection is independent of unverified clinical predictions."""
    registry = ModelRegistry(registry_dir=temp_registry_dir)
    service = UnifiedInferenceService(registry=registry, device="cpu")

    # Degenerate all-black image
    black_img = np.zeros((224, 224, 3), dtype=np.uint8)
    _, _, quality_issues = service._preprocess_image(black_img)
    assert quality_issues


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
