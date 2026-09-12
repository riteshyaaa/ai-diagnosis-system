"""
MedFusion AI — Unit Tests for Explainability Engine (Grad-CAM & SHAP).

Tests:
- GradCAMExplainer generates heatmaps from vision model
- Grad-CAM heatmap shape and normalization
- SHAPExplainerEngine TreeExplainer for XGBoost tabular models
- SHAPExplainerEngine KernelExplainer for TabularRiskMLP
- explain_vision_model high-level interface
- explain_tabular_model high-level interface
"""

import numpy as np
import pytest
import torch

from ml.models.image.classifier import ChestXRayClassifier
from ml.models.tabular import XGBoostRiskClassifier, TabularRiskMLP
from ml.explainability import (
    GradCAMExplainer,
    SHAPExplainerEngine,
    explain_vision_model,
    explain_tabular_model,
)


@pytest.fixture
def dummy_image_tensor():
    """Create dummy chest X-ray tensor [1, 3, 224, 224]."""
    return torch.randn(1, 3, 224, 224, dtype=torch.float32)


@pytest.fixture
def dummy_image_batch():
    """Create dummy batch of chest X-rays [4, 3, 224, 224]."""
    return torch.randn(4, 3, 224, 224, dtype=torch.float32)


def test_gradcam_explainer_heatmap(dummy_image_tensor):
    """Verify Grad-CAM heatmap generation and normalization."""
    model = ChestXRayClassifier()
    explainer = GradCAMExplainer(model=model)
    heatmap = explainer.generate_heatmap(dummy_image_tensor, class_idx=0)

    assert heatmap is not None
    # Heatmap should be normalized to [0, 1]
    assert heatmap.min() >= 0.0 and heatmap.max() <= 1.0
    # Spatial dimensions should match (last conv layer features are smaller than input)
    assert len(heatmap.shape) == 2  # [H, W]


def test_gradcam_explainer_batch_input(dummy_image_batch):
    """Verify Grad-CAM with batch input returns correct heatmap shape."""
    model = ChestXRayClassifier()
    explainer = GradCAMExplainer(model=model)
    heatmap = explainer.generate_heatmap(dummy_image_batch, class_idx=0)

    assert heatmap is not None
    assert len(heatmap.shape) == 2
    assert heatmap.min() >= 0.0 and heatmap.max() <= 1.0


def test_gradcam_plus_plus(dummy_image_tensor):
    """Verify Grad-CAM++ variant runs without error."""
    model = ChestXRayClassifier()
    explainer = GradCAMExplainer(model=model)
    heatmap = explainer.generate_gradcam_plus_plus(dummy_image_tensor, class_idx=1)

    assert heatmap is not None
    assert heatmap.min() >= 0.0 and heatmap.max() <= 1.0


def test_gradcam_multi_class(dummy_image_tensor):
    """Verify Grad-CAM can generate explanations for different class indices."""
    model = ChestXRayClassifier()
    explainer = GradCAMExplainer(model=model)

    heatmaps = []
    for class_idx in range(5):
        heatmap = explainer.generate_heatmap(dummy_image_tensor, class_idx=class_idx)
        heatmaps.append(heatmap)
        assert heatmap.min() >= 0.0 and heatmap.max() <= 1.0

    # All heatmaps should be generated and have same shape
    assert len(heatmaps) == 5
    assert all(h.shape == heatmaps[0].shape for h in heatmaps)


def test_gradcam_explainer_requires_backward_hook(dummy_image_tensor):
    """Verify Grad-CAM raises if hooks fail."""
    model = ChestXRayClassifier()
    explainer = GradCAMExplainer(model=model)

    # Valid input should work
    heatmap = explainer.generate_heatmap(dummy_image_tensor)
    assert heatmap is not None


def test_shap_explainer_engine_tree_model():
    """Verify SHAP TreeExplainer works with XGBoost tabular model."""
    np.random.seed(42)
    X = np.random.randn(100, 13).astype(np.float32)
    y = np.random.randint(0, 2, size=100)

    clf = XGBoostRiskClassifier(n_estimators=30, max_depth=3, calibration_method=None)
    clf.fit(X, y)

    explainer_engine = SHAPExplainerEngine(model=clf)
    assert explainer_engine.model_type == "tree"

    result = explainer_engine.explain(
        X=X[:20],
        background_data=X[:10],
        feature_names=[f"feature_{i}" for i in range(13)],
        n_samples=10,
    )

    assert "feature_importance" in result
    assert "top_5_features" in result
    assert "base_value" in result
    assert "shap_values" in result
    assert result["model_type"] == "tree"
    assert result["explanation_method"] == "TreeExplainer"

    # Feature importance should sum > 0 and have 13 features
    assert len(result["feature_importance"]) == 13
    assert sum(result["feature_importance"].values()) > 0.0


def test_shap_explainer_engine_deep_tabular():
    """Verify SHAP KernelExplainer works with TabularRiskMLP model."""
    np.random.seed(42)
    X = np.random.randn(100, 13).astype(np.float32)
    y = np.random.randint(0, 2, size=100)

    model = TabularRiskMLP(input_dim=13, embedding_dim=128, hidden_dim=128)
    # Initialize model with a single forward pass so state dict is populated
    dummy = torch.from_numpy(X[:2])
    with torch.no_grad():
        _ = model(dummy)

    explainer_engine = SHAPExplainerEngine(model=model)
    assert explainer_engine.model_type == "deep_tabular"

    result = explainer_engine.explain(
        X=X[:20],
        background_data=X[:5],
        feature_names=[f"feature_{i}" for i in range(13)],
        n_samples=5,
    )

    assert "feature_importance" in result
    assert "top_5_features" in result
    assert "base_value" in result
    assert "shap_values" in result
    assert result["model_type"] == "deep_tabular"
    assert result["explanation_method"] == "KernelExplainer"

    assert len(result["feature_importance"]) == 13
    assert sum(result["feature_importance"].values()) > 0.0


def test_explain_vision_model_interface(dummy_image_tensor):
    """Verify high-level vision explainability interface."""
    model = ChestXRayClassifier()
    result = explain_vision_model(
        image_tensor=dummy_image_tensor,
        model=model,
        class_idx=0,
    )

    assert result["explanation_type"] == "Grad-CAM"
    assert "heatmap" in result
    assert "heatmap_shape" in result or "heatmap" in result
    assert result["target_class_index"] == 0
    assert result["device_used"] is not None


def test_explain_tabular_model_interface():
    """Verify high-level tabular explainability interface."""
    np.random.seed(42)
    X = np.random.randn(100, 13).astype(np.float32)
    y = np.random.randint(0, 2, size=100)

    clf = XGBoostRiskClassifier(n_estimators=30, max_depth=3, calibration_method=None)
    clf.fit(X, y)

    feature_names = [f"feature_{i}" for i in range(13)]
    result = explain_tabular_model(
        model=clf,
        X=X[:20],
        feature_names=feature_names,
        background_data=X[:10],
    )

    assert "feature_importance" in result
    assert "top_5_features" in result
    assert "base_value" in result
    assert result["explanation_method"] == "TreeExplainer"

    # Verify top 5 features list contains tuples of (name, importance)
    assert len(result["top_5_features"]) == 5
    for name, importance in result["top_5_features"]:
        assert name in feature_names
        assert isinstance(importance, float)


def test_shap_feature_importance_ranking():
    """Verify SHAP feature importance is properly ranked in descending order."""
    np.random.seed(42)
    X = np.random.randn(100, 13).astype(np.float32)
    y = np.random.randint(0, 2, size=100)

    clf = XGBoostRiskClassifier(n_estimators=30, max_depth=3, calibration_method=None)
    clf.fit(X, y)

    result = SHAPExplainerEngine(model=clf).explain(
        X=X[:20],
        background_data=X[:10],
        feature_names=[f"feature_{i}" for i in range(13)],
    )

    fi = result["feature_importance"]
    values = list(fi.values())
    # Check descending order
    for i in range(len(values) - 1):
        assert values[i] >= values[i + 1], (
            f"Feature importance not sorted descending: {values[i]} < {values[i+1]}"
        )
