"""
MedFusion AI — Unit Tests for Multimodal Late-Fusion Model & Uncertainty Calibration.

Tests:
- GatedMultimodalFusion layer with both modalities, image-only, and tabular-only
- CrossModalAttentionFusion cross-attention layer
- MultimodalLateFusionModel forward pass (multi-task pathology & risk)
- Missing modality robustness
- Shannon entropy uncertainty estimation & cross-modal conflict abstention logic
- Inference prediction structuring
- Checkpoint persistence and reconstruction
"""

import numpy as np
import pytest
import torch

from ml.models.fusion import (
    CrossModalAttentionFusion,
    GatedMultimodalFusion,
    MultimodalLateFusionModel,
)


@pytest.fixture
def dummy_embeddings():
    """Create batch of synthetic 512-dim vision and 128-dim tabular embeddings."""
    batch_size = 4
    img_emb = torch.randn(batch_size, 512, dtype=torch.float32)
    tab_emb = torch.randn(batch_size, 128, dtype=torch.float32)
    return img_emb, tab_emb


def test_gated_multimodal_fusion_both_modalities(dummy_embeddings):
    """Verify gated fusion output dimension and valid gate weights [0, 1]."""
    img_emb, tab_emb = dummy_embeddings
    fusion_layer = GatedMultimodalFusion(image_dim=512, tabular_dim=128, fusion_dim=256)

    fused, gates = fusion_layer(img_emb, tab_emb)

    assert fused.shape == (4, 256)
    assert gates.shape == (4, 2)
    assert not torch.isnan(fused).any()
    assert (gates >= 0.0).all() and (gates <= 1.0).all()


def test_gated_multimodal_fusion_missing_modalities(dummy_embeddings):
    """Verify gated fusion handles single-modality inputs gracefully."""
    img_emb, tab_emb = dummy_embeddings
    fusion_layer = GatedMultimodalFusion(image_dim=512, tabular_dim=128, fusion_dim=256)

    # Image only (missing tabular)
    fused_img_only, gates_img = fusion_layer(img_emb, None)
    assert fused_img_only.shape == (4, 256)
    assert (gates_img[:, 0] == 1.0).all()

    # Tabular only (missing image)
    fused_tab_only, gates_tab = fusion_layer(None, tab_emb)
    assert fused_tab_only.shape == (4, 256)
    assert (gates_tab[:, 1] == 1.0).all()

    # Neither provided
    with pytest.raises(ValueError, match="At least one modality"):
        fusion_layer(None, None)


def test_cross_modal_attention_fusion(dummy_embeddings):
    """Verify bidirectional multihead cross-attention layer."""
    img_emb, tab_emb = dummy_embeddings
    fusion_dim = 256
    proj_img = torch.nn.Linear(512, fusion_dim)(img_emb)
    proj_tab = torch.nn.Linear(128, fusion_dim)(tab_emb)

    attn_layer = CrossModalAttentionFusion(image_dim=512, tabular_dim=128, fusion_dim=fusion_dim)
    fused = attn_layer(proj_img, proj_tab)

    assert fused.shape == (4, fusion_dim)
    assert not torch.isnan(fused).any()


def test_multimodal_late_fusion_model_forward(dummy_embeddings):
    """Verify full late-fusion model forward pass with multi-task heads."""
    img_emb, tab_emb = dummy_embeddings
    model = MultimodalLateFusionModel(
        image_embedding_dim=512,
        tabular_embedding_dim=128,
        fusion_dim=256,
        fusion_method="gated",
    )

    out = model(img_emb, tab_emb, return_embeddings=True)

    assert "pathology_logits" in out
    assert "pathology_probs" in out
    assert "risk_logits" in out
    assert "risk_probs" in out
    assert "modality_gates" in out
    assert "fused_embedding" in out

    # Verify output shapes (5 pathology classes, 1 risk class)
    assert out["pathology_probs"].shape == (4, 5)
    assert out["risk_probs"].shape == (4, 1)
    assert (out["pathology_probs"] >= 0.0).all() and (out["pathology_probs"] <= 1.0).all()
    assert (out["risk_probs"] >= 0.0).all() and (out["risk_probs"] <= 1.0).all()


def test_multimodal_late_fusion_missing_modality_inference(dummy_embeddings):
    """Verify model can perform inference when either modality is omitted."""
    img_emb, tab_emb = dummy_embeddings
    model = MultimodalLateFusionModel(fusion_method="gated")

    # Image only
    out_img = model(image_embeddings=img_emb, tabular_embeddings=None)
    assert out_img["pathology_probs"].shape == (4, 5)
    assert out_img["risk_probs"].shape == (4, 1)

    # Tabular only
    out_tab = model(image_embeddings=None, tabular_embeddings=tab_emb)
    assert out_tab["pathology_probs"].shape == (4, 5)
    assert out_tab["risk_probs"].shape == (4, 1)


def test_uncertainty_and_safety_abstention():
    """Verify Shannon entropy uncertainty quantification and cross-modal conflict detection."""
    model = MultimodalLateFusionModel()

    # Case 1: High confidence prediction (no abstention)
    diag_confident = model.compute_uncertainty_and_abstention(
        pathology_probs=np.array([0.02, 0.01, 0.95, 0.03, 0.01]),
        risk_prob=0.92,
        aux_img_risk_prob=0.90,
        aux_tab_risk_prob=0.88,
        uncertainty_threshold=0.65,
        conflict_threshold=0.40,
    )
    assert diag_confident["abstain"] is False
    assert diag_confident["overall_uncertainty"] < 0.5
    assert diag_confident["confidence"] > 0.5
    assert diag_confident["has_conflict"] is False

    # Case 2: Borderline / High uncertainty prediction (triggers abstention)
    diag_uncertain = model.compute_uncertainty_and_abstention(
        pathology_probs=np.array([0.5, 0.5, 0.5, 0.5, 0.5]),
        risk_prob=0.5,
        aux_img_risk_prob=0.5,
        aux_tab_risk_prob=0.5,
        uncertainty_threshold=0.65,
    )
    assert diag_uncertain["abstain"] is True
    assert any("uncertainty" in r.lower() or "borderline" in r.lower() for r in diag_uncertain["abstention_reasons"])

    # Case 3: Conflicting modalities (Vision says high risk, Tabular says low risk)
    diag_conflict = model.compute_uncertainty_and_abstention(
        pathology_probs=np.array([0.1, 0.1, 0.8, 0.1, 0.1]),
        risk_prob=0.75,
        aux_img_risk_prob=0.85,
        aux_tab_risk_prob=0.15,  # Gap = 0.70 > 0.40
        conflict_threshold=0.40,
    )
    assert diag_conflict["abstain"] is True
    assert diag_conflict["has_conflict"] is True
    assert any("disagreement" in r.lower() for r in diag_conflict["abstention_reasons"])


def test_predict_structured_output(dummy_embeddings):
    """Verify predict method returns structured diagnostic summaries with safety flags."""
    img_emb, tab_emb = dummy_embeddings
    model = MultimodalLateFusionModel()

    preds = model.predict(
        image_embeddings=img_emb.numpy(),
        tabular_embeddings=tab_emb.numpy(),
        threshold=0.5,
    )

    assert len(preds) == 4
    first = preds[0]
    assert "risk_score" in first
    assert "risk_prediction" in first
    assert "pathology_findings" in first
    assert len(first["pathology_findings"]) == 5
    assert "Atelectasis" in first["pathology_findings"]
    assert "uncertainty" in first
    assert "abstain" in first["uncertainty"]
    assert "modalities_present" in first
    assert first["modalities_present"] == ["image", "tabular"]


def test_multimodal_late_fusion_checkpoint_roundtrip(dummy_embeddings, tmp_path):
    """Verify serialization and deserialization of the multimodal model."""
    img_emb, tab_emb = dummy_embeddings
    ckpt_file = tmp_path / "fusion_model.pt"

    model = MultimodalLateFusionModel(fusion_method="gated")
    model.eval()
    with torch.no_grad():
        orig_out = model(img_emb, tab_emb)

    model.save_checkpoint(ckpt_file)
    assert ckpt_file.exists()

    loaded_model = MultimodalLateFusionModel.load_checkpoint(ckpt_file)
    loaded_model.eval()
    with torch.no_grad():
        loaded_out = loaded_model(img_emb, tab_emb)

    torch.testing.assert_close(orig_out["pathology_probs"], loaded_out["pathology_probs"])
    torch.testing.assert_close(orig_out["risk_probs"], loaded_out["risk_probs"])
