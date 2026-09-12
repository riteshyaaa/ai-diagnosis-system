"""
MedFusion AI — Unit Tests for Chest Radiograph Vision Deep Learning Models.

Tests:
- DenseNet121Backbone feature extraction & Grad-CAM layer access
- EfficientNetB0Backbone feature extraction & Grad-CAM layer access
- ChestXRayClassifier multi-label forward pass & probability shapes
- Freezing and unfreezing of backbone weights
- Model checkpoint serialization and deserialization roundtrip
- Structured prediction outputs
"""

import numpy as np
import pytest
import torch

from ml.models.image import (
    BaseVisionBackbone,
    ChestXRayClassifier,
    DenseNet121Backbone,
    EfficientNetB0Backbone,
)


@pytest.fixture
def dummy_radiograph_batch():
    """Batch of 2 synthetic radiographs [batch_size=2, channels=3, height=224, width=224]."""
    return torch.randn(2, 3, 224, 224, dtype=torch.float32)


def test_densenet121_backbone_feature_extraction(dummy_radiograph_batch):
    """Verify DenseNet121 extracts projected 512-dim embedding tensor."""
    backbone = DenseNet121Backbone(pretrained=False, embedding_dim=512)
    embeddings = backbone.extract_features(dummy_radiograph_batch)

    assert isinstance(embeddings, torch.Tensor)
    assert embeddings.shape == (2, 512)
    assert not torch.isnan(embeddings).any()

    # Verify Grad-CAM target layer is valid nn.Module
    conv_layer = backbone.get_last_conv_layer()
    assert isinstance(conv_layer, torch.nn.Module)


def test_efficientnet_b0_backbone_feature_extraction(dummy_radiograph_batch):
    """Verify EfficientNet-B0 extracts projected 512-dim embedding tensor."""
    backbone = EfficientNetB0Backbone(pretrained=False, embedding_dim=512)
    embeddings = backbone.extract_features(dummy_radiograph_batch)

    assert isinstance(embeddings, torch.Tensor)
    assert embeddings.shape == (2, 512)
    assert not torch.isnan(embeddings).any()

    conv_layer = backbone.get_last_conv_layer()
    assert isinstance(conv_layer, torch.nn.Module)


def test_classifier_multi_label_forward(dummy_radiograph_batch):
    """Verify ChestXRayClassifier forward pass returns logits, scaled logits, and probabilities."""
    model = ChestXRayClassifier(
        backbone_name="densenet121",
        num_classes=5,
        class_names=["Atelectasis", "Cardiomegaly", "Effusion", "Infiltration", "Mass"],
        embedding_dim=512,
        multi_label=True,
        pretrained=False,
    )

    out = model(dummy_radiograph_batch, return_embeddings=True)
    assert "logits" in out
    assert "probabilities" in out
    assert "embeddings" in out

    assert out["logits"].shape == (2, 5)
    assert out["probabilities"].shape == (2, 5)
    assert out["embeddings"].shape == (2, 512)

    # Sigmoid output in [0, 1] range
    probs = out["probabilities"]
    assert (probs >= 0.0).all() and (probs <= 1.0).all()


def test_classifier_freeze_and_unfreeze():
    """Verify freezing/unfreezing mechanism for transfer learning."""
    model = ChestXRayClassifier(backbone_name="densenet121", pretrained=False)

    # Initial state: gradients enabled
    assert any(p.requires_grad for p in model.backbone.parameters())

    # Freeze backbone
    model.freeze_backbone()
    assert all(not p.requires_grad for p in model.backbone.parameters())
    # Classifier head should still be trainable
    assert model.classifier.weight.requires_grad is True

    # Unfreeze backbone
    model.unfreeze_backbone()
    assert all(p.requires_grad for p in model.backbone.parameters())


def test_classifier_structured_predict(dummy_radiograph_batch):
    """Verify structured clinical inference output format."""
    model = ChestXRayClassifier(
        backbone_name="densenet121",
        class_names=["Cardiomegaly", "Effusion"],
        num_classes=2,
        pretrained=False,
    )

    predictions = model.predict(dummy_radiograph_batch, threshold=0.5)
    assert len(predictions) == 2  # Batch size
    first_pred = predictions[0]

    assert "findings" in first_pred
    assert "max_risk_score" in first_pred
    assert "Cardiomegaly" in first_pred["findings"]
    assert "Effusion" in first_pred["findings"]
    assert isinstance(first_pred["findings"]["Cardiomegaly"]["probability"], float)
    assert isinstance(first_pred["findings"]["Cardiomegaly"]["present"], bool)


def test_classifier_checkpoint_save_and_load(tmp_path, dummy_radiograph_batch):
    """Verify serialization and deserialization of model state."""
    ckpt_path = tmp_path / "densenet_test.pt"

    model = ChestXRayClassifier(
        backbone_name="densenet121",
        class_names=["Atelectasis", "Cardiomegaly", "Effusion", "Infiltration", "Mass"],
        embedding_dim=256,
        pretrained=False,
    )
    model.eval()
    with torch.no_grad():
        orig_out = model(dummy_radiograph_batch)

    # Save checkpoint
    model.save_checkpoint(ckpt_path)
    assert ckpt_path.exists()

    # Load checkpoint
    loaded_model = ChestXRayClassifier.load_checkpoint(ckpt_path)
    loaded_model.eval()
    with torch.no_grad():
        loaded_out = loaded_model(dummy_radiograph_batch)

    torch.testing.assert_close(orig_out["logits"], loaded_out["logits"])
    torch.testing.assert_close(orig_out["probabilities"], loaded_out["probabilities"])
