"""
MedFusion AI — Multimodal Late-Fusion Deep Learning Architecture.

Integrates:
- 512-dimensional Chest Radiograph visual embeddings (DenseNet-121 / EfficientNet-B0)
- 128-dimensional Structured Tabular clinical embeddings (TabularRiskMLP)
- Gated cross-modal fusion with dynamic missing-modality robustness
- Multi-task clinical diagnosis: thoracic pathology multi-label & composite disease risk
- Temperature-scaled uncertainty quantification and automated safety abstention
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from ml.models.image.classifier import ChestXRayClassifier
from ml.models.tabular.neural_models import TabularRiskMLP


class CrossModalAttentionFusion(nn.Module):
    """
    Cross-Modal Attention Block.
    Computes bidirectional cross-attention between vision and tabular feature subspaces.
    """

    def __init__(
        self,
        image_dim: int = 512,
        tabular_dim: int = 128,
        fusion_dim: int = 256,
        num_heads: int = 4,
        dropout_rate: float = 0.2,
    ):
        super().__init__()
        self.fusion_dim = fusion_dim
        self.num_heads = num_heads

        # Projections into common latent subspace
        self.proj_img = nn.Linear(image_dim, fusion_dim)
        self.proj_tab = nn.Linear(tabular_dim, fusion_dim)

        # Multi-head cross attention: Query=Tabular, Key/Value=Image
        self.cross_attn_tab_to_img = nn.MultiheadAttention(
            embed_dim=fusion_dim,
            num_heads=num_heads,
            dropout=dropout_rate,
            batch_first=True,
        )
        # Multi-head cross attention: Query=Image, Key/Value=Tabular
        self.cross_attn_img_to_tab = nn.MultiheadAttention(
            embed_dim=fusion_dim,
            num_heads=num_heads,
            dropout=dropout_rate,
            batch_first=True,
        )

        self.norm_img = nn.LayerNorm(fusion_dim)
        self.norm_tab = nn.LayerNorm(fusion_dim)
        self.dropout = nn.Dropout(dropout_rate)

        # Output projection
        self.out_proj = nn.Sequential(
            nn.Linear(fusion_dim * 2, fusion_dim),
            nn.BatchNorm1d(fusion_dim),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Dropout(dropout_rate),
        )

    def forward(self, h_img: torch.Tensor, h_tab: torch.Tensor) -> torch.Tensor:
        """
        Args:
            h_img: Raw or projected image tensor [batch_size, image_dim or fusion_dim]
            h_tab: Raw or projected tabular tensor [batch_size, tabular_dim or fusion_dim]
        Returns:
            Fused multimodal representation [batch_size, fusion_dim]
        """
        p_img = self.proj_img(h_img) if h_img.size(-1) != self.fusion_dim else h_img
        p_tab = self.proj_tab(h_tab) if h_tab.size(-1) != self.fusion_dim else h_tab

        seq_img = p_img.unsqueeze(1)
        seq_tab = p_tab.unsqueeze(1)

        # Cross attention
        attn_img, _ = self.cross_attn_img_to_tab(seq_img, seq_tab, seq_tab)
        attn_tab, _ = self.cross_attn_tab_to_img(seq_tab, seq_img, seq_img)

        # Residual connections + norm
        f_img = self.norm_img(p_img + attn_img.squeeze(1))
        f_tab = self.norm_tab(p_tab + attn_tab.squeeze(1))

        combined = torch.cat([f_img, f_tab], dim=-1)
        return self.out_proj(combined)


class GatedMultimodalFusion(nn.Module):
    """
    Adaptive Cross-Modal Gating Layer.
    Learns dynamic modality weighting coefficients g_img and g_tab in [0, 1]
    based on the feature quality and relevance of each clinical stream.
    """

    def __init__(
        self,
        image_dim: int = 512,
        tabular_dim: int = 128,
        fusion_dim: int = 256,
        dropout_rate: float = 0.2,
    ):
        super().__init__()
        self.fusion_dim = fusion_dim

        # Input projections
        self.proj_img = nn.Sequential(
            nn.Linear(image_dim, fusion_dim),
            nn.BatchNorm1d(fusion_dim),
            nn.LeakyReLU(0.1, inplace=True),
        )
        self.proj_tab = nn.Sequential(
            nn.Linear(tabular_dim, fusion_dim),
            nn.BatchNorm1d(fusion_dim),
            nn.LeakyReLU(0.1, inplace=True),
        )

        # Modality gating network
        self.gate_net = nn.Sequential(
            nn.Linear(image_dim + tabular_dim, fusion_dim),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Dropout(dropout_rate),
            nn.Linear(fusion_dim, 2),
            nn.Sigmoid(),
        )

        # Combined projection block
        self.fusion_block = nn.Sequential(
            nn.Linear(fusion_dim * 2, fusion_dim),
            nn.BatchNorm1d(fusion_dim),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Dropout(dropout_rate),
            nn.Linear(fusion_dim, fusion_dim),
            nn.BatchNorm1d(fusion_dim),
        )
        self.res_act = nn.LeakyReLU(0.1, inplace=True)

    def forward(
        self,
        h_img: Optional[torch.Tensor],
        h_tab: Optional[torch.Tensor],
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with missing-modality handling.
        Returns:
            fused_embedding: [batch_size, fusion_dim]
            gates: [batch_size, 2] containing (gate_img, gate_tab)
        """
        if h_img is None and h_tab is None:
            raise ValueError("At least one modality (image or tabular) must be provided.")

        batch_size = h_img.size(0) if h_img is not None else h_tab.size(0)
        device = h_img.device if h_img is not None else h_tab.device

        # Case 1: Tabular only missing image
        if h_img is None:
            p_tab = self.proj_tab(h_tab)
            zeros = torch.zeros_like(p_tab)
            fused = self.res_act(self.fusion_block(torch.cat([zeros, p_tab], dim=-1)))
            gates = torch.zeros(batch_size, 2, device=device)
            gates[:, 1] = 1.0
            return fused, gates

        # Case 2: Image only missing tabular
        if h_tab is None:
            p_img = self.proj_img(h_img)
            zeros = torch.zeros_like(p_img)
            fused = self.res_act(self.fusion_block(torch.cat([p_img, zeros], dim=-1)))
            gates = torch.zeros(batch_size, 2, device=device)
            gates[:, 0] = 1.0
            return fused, gates

        # Case 3: Both modalities present
        p_img = self.proj_img(h_img)
        p_tab = self.proj_tab(h_tab)

        concat_raw = torch.cat([h_img, h_tab], dim=-1)
        gates = self.gate_net(concat_raw)

        gate_img = gates[:, 0:1]
        gate_tab = gates[:, 1:2]

        gated_img = p_img * gate_img
        gated_tab = p_tab * gate_tab

        combined = torch.cat([gated_img, gated_tab], dim=-1)
        fused = self.res_act(self.fusion_block(combined))
        return fused, gates


class MultimodalLateFusionModel(nn.Module):
    """
    Enterprise Deep Multimodal Clinical Diagnostic & Risk Assessment Architecture.

    Fuses:
    1. Visual embeddings extracted from Chest Radiographs (512-dim)
    2. Tabular clinical embeddings extracted from structured vitals/labs (128-dim)

    Provides:
    - Multi-label thoracic pathology classification (Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass)
    - Primary cardiovascular / composite disease risk classification
    - Calibrated probabilities with learnable temperature scaling
    - Cross-modal conflict / disagreement detection and Shannon entropy uncertainty estimation
    - Automated safety abstention engine with configurable clinical risk thresholds
    """

    DEFAULT_PATHOLOGIES = [
        "Atelectasis",
        "Cardiomegaly",
        "Effusion",
        "Infiltration",
        "Mass",
    ]

    def __init__(
        self,
        image_embedding_dim: int = 512,
        tabular_embedding_dim: int = 128,
        fusion_dim: int = 256,
        pathology_classes: Optional[List[str]] = None,
        fusion_method: str = "gated",
        dropout_rate: float = 0.2,
        image_backbone: Optional[str] = "densenet121",
        num_image_classes: Optional[int] = 5,
        num_tabular_features: Optional[int] = 13,
        fusion_strategy: Optional[str] = None,
        fusion_hidden_dim: Optional[int] = None,
        pretrained_vision: bool = False,
    ):
        super().__init__()
        self.image_embedding_dim = image_embedding_dim
        self.tabular_embedding_dim = tabular_embedding_dim
        self.fusion_dim = fusion_hidden_dim or fusion_dim
        self.pathology_classes = pathology_classes or self.DEFAULT_PATHOLOGIES
        self.class_names = self.pathology_classes
        self.num_pathologies = len(self.pathology_classes)
        self.num_classes = self.num_pathologies

        strategy = fusion_strategy or fusion_method or "gated"
        self.fusion_strategy = strategy.lower()
        self.fusion_method = self.fusion_strategy

        # Unimodal backbones
        self.image_model = ChestXRayClassifier(
            backbone_name=image_backbone or "densenet121",
            num_classes=num_image_classes or self.num_pathologies,
            class_names=self.pathology_classes,
            embedding_dim=image_embedding_dim,
            pretrained=pretrained_vision,
        )

        self.tabular_model = TabularRiskMLP(
            input_dim=num_tabular_features or 13,
            embedding_dim=tabular_embedding_dim,
        )

        # Fusion layer
        if self.fusion_method == "gated":
            self.fusion_layer = GatedMultimodalFusion(
                image_dim=image_embedding_dim,
                tabular_dim=tabular_embedding_dim,
                fusion_dim=self.fusion_dim,
                dropout_rate=dropout_rate,
            )
        elif self.fusion_method in ("cross_attention", "attention"):
            self.fusion_layer = CrossModalAttentionFusion(
                image_dim=image_embedding_dim,
                tabular_dim=tabular_embedding_dim,
                fusion_dim=self.fusion_dim,
                dropout_rate=dropout_rate,
            )
        elif self.fusion_method == "concat":
            self.fusion_layer = nn.Sequential(
                nn.Linear(image_embedding_dim + tabular_embedding_dim, self.fusion_dim),
                nn.BatchNorm1d(self.fusion_dim),
                nn.LeakyReLU(0.1, inplace=True),
                nn.Dropout(dropout_rate),
            )
        else:
            raise ValueError(
                f"Unsupported fusion method '{strategy}'. Choose 'gated', 'attention', or 'concat'."
            )

        # Unimodal auxiliary risk prediction heads (used for detecting cross-modal divergence/conflict)
        self.aux_img_risk_head = nn.Linear(image_embedding_dim, 1)
        self.aux_tab_risk_head = nn.Linear(tabular_embedding_dim, 1)

        # Joint Multimodal Diagnostic Heads
        self.pathology_head = nn.Sequential(
            nn.Linear(self.fusion_dim, self.fusion_dim // 2),
            nn.BatchNorm1d(self.fusion_dim // 2),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Dropout(dropout_rate),
            nn.Linear(self.fusion_dim // 2, self.num_pathologies),
        )

        self.risk_head = nn.Sequential(
            nn.Linear(self.fusion_dim, self.fusion_dim // 2),
            nn.BatchNorm1d(self.fusion_dim // 2),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Dropout(dropout_rate),
            nn.Linear(self.fusion_dim // 2, 1),
        )

        # Temperature scaling parameters for calibration
        self.temperature_pathology = nn.Parameter(torch.ones(1))
        self.temperature_risk = nn.Parameter(torch.ones(1))

    def freeze_vision_backbone(self, freeze: bool = True) -> None:
        """Freeze or unfreeze vision backbone parameters."""
        if hasattr(self.image_model, "freeze_backbone"):
            if freeze:
                self.image_model.freeze_backbone()
            else:
                self.image_model.unfreeze_backbone()
        elif hasattr(self.image_model, "backbone"):
            self.image_model.backbone.freeze(freeze)

    def freeze_tabular_backbone(self, freeze: bool = True) -> None:
        """Freeze or unfreeze tabular backbone parameters."""
        if hasattr(self.tabular_model, "freeze"):
            self.tabular_model.freeze(freeze)

    def fuse_embeddings(
        self,
        image_embeddings: Optional[torch.Tensor] = None,
        tabular_embeddings: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Fuse unimodal embedding representations into a shared clinical representation.
        Returns:
            fused: [batch_size, fusion_dim]
            gates: [batch_size, 2] or None
        """
        if self.fusion_method == "gated":
            return self.fusion_layer(image_embeddings, tabular_embeddings)
        elif self.fusion_method in ("cross_attention", "attention"):
            if image_embeddings is None or tabular_embeddings is None:
                raise ValueError("Cross-attention fusion requires both image and tabular embeddings.")
            fused = self.fusion_layer(image_embeddings, tabular_embeddings)
            return fused, None
        else:  # concat
            if image_embeddings is None or tabular_embeddings is None:
                raise ValueError("Concatenation fusion requires both image and tabular embeddings.")
            concat_emb = torch.cat([image_embeddings, tabular_embeddings], dim=-1)
            fused = self.fusion_layer(concat_emb)
            return fused, None

    def forward(
        self,
        image_input: Optional[torch.Tensor] = None,
        tabular_input: Optional[torch.Tensor] = None,
        return_embeddings: bool = False,
        image_embeddings: Optional[torch.Tensor] = None,
        tabular_embeddings: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass supporting both raw inputs and pre-extracted embeddings.
        Args:
            image_input: Raw image tensor [batch, 3, H, W] or embeddings [batch, image_dim]
            tabular_input: Raw tabular tensor [batch, num_features] or embeddings [batch, tabular_dim]
            return_embeddings: Whether to return internal feature embeddings
            image_embeddings: Keyword alias for image_input (for pre-computed embeddings)
            tabular_embeddings: Keyword alias for tabular_input (for pre-computed embeddings)
        """
        img_in = image_input if image_input is not None else image_embeddings
        tab_in = tabular_input if tabular_input is not None else tabular_embeddings

        # 1. Process image representation
        img_emb = None
        if img_in is not None:
            if img_in.dim() == 4:
                img_emb = self.image_model.extract_features(img_in)
            else:
                img_emb = img_in

        # 2. Process tabular representation
        tab_emb = None
        if tab_in is not None:
            if tab_in.dim() == 2 and tab_in.shape[1] == self.tabular_model.input_dim and self.tabular_model.input_dim != self.tabular_embedding_dim:
                tab_emb = self.tabular_model.extract_features(tab_in)
            elif tab_in.dim() == 2 and tab_in.shape[1] == self.tabular_embedding_dim:
                tab_emb = tab_in
            else:
                tab_emb = self.tabular_model.extract_features(tab_in)

        fused_embedding, gates = self.fuse_embeddings(img_emb, tab_emb)

        # Multi-label pathology classification
        pathology_logits = self.pathology_head(fused_embedding)
        temp_path = torch.clamp(self.temperature_pathology, min=0.01)
        pathology_probs = torch.sigmoid(pathology_logits / temp_path)

        # Primary composite risk classification
        risk_logits = self.risk_head(fused_embedding)
        temp_risk = torch.clamp(self.temperature_risk, min=0.01)
        risk_probs = torch.sigmoid(risk_logits / temp_risk)

        out = {
            "pathology_logits": pathology_logits,
            "pathology_probs": pathology_probs,
            "risk_logits": risk_logits,
            "risk_probs": risk_probs,
            "risk_prob": risk_probs,  # Alias for compatibility
        }

        if gates is not None:
            out["modality_gates"] = gates

        if return_embeddings:
            out["fused_embedding"] = fused_embedding
            if img_emb is not None:
                out["image_embedding"] = img_emb
            if tab_emb is not None:
                out["tabular_embedding"] = tab_emb

        # Auxiliary unimodal risk predictions for conflict/divergence computation
        if img_emb is not None:
            out["aux_img_risk_prob"] = torch.sigmoid(self.aux_img_risk_head(img_emb))
        if tab_emb is not None:
            out["aux_tab_risk_prob"] = torch.sigmoid(self.aux_tab_risk_head(tab_emb))

        return out

    def compute_uncertainty_and_abstention(
        self,
        pathology_probs: np.ndarray,
        risk_prob: float,
        aux_img_risk_prob: Optional[float] = None,
        aux_tab_risk_prob: Optional[float] = None,
        uncertainty_threshold: float = 0.65,
        conflict_threshold: float = 0.40,
        min_confidence: float = 0.55,
    ) -> Dict[str, Any]:
        """
        Compute Shannon entropy uncertainty, cross-modal conflict score, and safety abstention decision.
        """
        eps = 1e-7
        p = np.clip(risk_prob, eps, 1.0 - eps)
        risk_entropy = float(-(p * np.log2(p) + (1 - p) * np.log2(1 - p)))

        p_path = np.clip(pathology_probs, eps, 1.0 - eps)
        pathology_entropy = float(np.mean(-(p_path * np.log2(p_path) + (1 - p_path) * np.log2(1 - p_path))))

        overall_uncertainty = round(float(0.6 * risk_entropy + 0.4 * pathology_entropy), 4)
        confidence = round(float(1.0 - overall_uncertainty), 4)

        conflict_score = 0.0
        has_conflict = False
        if aux_img_risk_prob is not None and aux_tab_risk_prob is not None:
            conflict_score = round(float(abs(aux_img_risk_prob - aux_tab_risk_prob)), 4)
            if conflict_score >= conflict_threshold:
                has_conflict = True

        abstain = False
        abstention_reasons = []

        if overall_uncertainty >= uncertainty_threshold:
            abstain = True
            abstention_reasons.append(
                f"High predictive uncertainty (entropy={overall_uncertainty:.2f} >= {uncertainty_threshold:.2f})"
            )

        if has_conflict:
            abstain = True
            abstention_reasons.append(
                f"Cross-modal clinical disagreement (image-tabular risk gap={conflict_score:.2f} >= {conflict_threshold:.2f})"
            )

        if abs(risk_prob - 0.5) < (min_confidence - 0.5):
            abstain = True
            abstention_reasons.append(
                f"Borderline diagnostic risk score ({risk_prob:.2f}), clinician manual review mandatory"
            )

        return {
            "abstain": abstain,
            "abstention_reasons": abstention_reasons,
            "overall_uncertainty": overall_uncertainty,
            "risk_entropy": round(risk_entropy, 4),
            "pathology_entropy": round(pathology_entropy, 4),
            "confidence": confidence,
            "conflict_score": conflict_score,
            "has_conflict": has_conflict,
        }

    def predict(
        self,
        image_embeddings: Optional[Union[torch.Tensor, np.ndarray]] = None,
        tabular_embeddings: Optional[Union[torch.Tensor, np.ndarray]] = None,
        threshold: float = 0.5,
        uncertainty_threshold: float = 0.65,
        conflict_threshold: float = 0.40,
    ) -> List[Dict[str, Any]]:
        """
        High-level inference method generating structured clinical predictions with safety flags.
        """
        self.eval()
        device = next(self.parameters()).device

        if isinstance(image_embeddings, np.ndarray):
            image_embeddings = torch.from_numpy(image_embeddings.astype(np.float32)).to(device)
        elif image_embeddings is not None:
            image_embeddings = image_embeddings.to(device)

        if isinstance(tabular_embeddings, np.ndarray):
            tabular_embeddings = torch.from_numpy(tabular_embeddings.astype(np.float32)).to(device)
        elif tabular_embeddings is not None:
            tabular_embeddings = tabular_embeddings.to(device)

        batch_size = (
            image_embeddings.size(0)
            if image_embeddings is not None
            else (tabular_embeddings.size(0) if tabular_embeddings is not None else 0)
        )

        with torch.no_grad():
            outputs = self.forward(
                image_input=image_embeddings,
                tabular_input=tabular_embeddings,
                return_embeddings=True,
            )

            path_probs_all = outputs["pathology_probs"].cpu().numpy()
            risk_probs_all = outputs["risk_probs"].cpu().numpy().ravel()
            gates_all = (
                outputs["modality_gates"].cpu().numpy()
                if "modality_gates" in outputs
                else None
            )
            aux_img_risk = (
                outputs["aux_img_risk_prob"].cpu().numpy().ravel()
                if "aux_img_risk_prob" in outputs
                else None
            )
            aux_tab_risk = (
                outputs["aux_tab_risk_prob"].cpu().numpy().ravel()
                if "aux_tab_risk_prob" in outputs
                else None
            )

        results = []
        for idx in range(batch_size):
            p_path = path_probs_all[idx]
            p_risk = float(risk_probs_all[idx])
            img_aux = float(aux_img_risk[idx]) if aux_img_risk is not None else None
            tab_aux = float(aux_tab_risk[idx]) if aux_tab_risk is not None else None

            findings = {}
            for c_idx, name in enumerate(self.pathology_classes):
                prob = float(p_path[c_idx])
                findings[name] = {
                    "probability": round(prob, 4),
                    "present": prob >= threshold,
                }

            modality_weights = {}
            if gates_all is not None:
                modality_weights["image_weight"] = round(float(gates_all[idx][0]), 4)
                modality_weights["tabular_weight"] = round(float(gates_all[idx][1]), 4)

            uncertainty_info = self.compute_uncertainty_and_abstention(
                pathology_probs=p_path,
                risk_prob=p_risk,
                aux_img_risk_prob=img_aux,
                aux_tab_risk_prob=tab_aux,
                uncertainty_threshold=uncertainty_threshold,
                conflict_threshold=conflict_threshold,
            )

            results.append({
                "risk_score": round(p_risk, 4),
                "risk_prediction": int(p_risk >= threshold),
                "pathology_findings": findings,
                "modality_weights": modality_weights,
                "uncertainty": uncertainty_info,
                "modalities_present": [
                    m
                    for m, present in [
                        ("image", image_embeddings is not None),
                        ("tabular", tabular_embeddings is not None),
                    ]
                    if present
                ],
            })

        return results

    def save_checkpoint(self, path: Union[str, Path]) -> None:
        """Serialize model weights and hyperparameters."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.state_dict(),
                "image_embedding_dim": self.image_embedding_dim,
                "tabular_embedding_dim": self.tabular_embedding_dim,
                "fusion_dim": self.fusion_dim,
                "pathology_classes": self.pathology_classes,
                "fusion_strategy": self.fusion_strategy,
            },
            dest,
        )

    @classmethod
    def load_checkpoint(
        cls,
        path: Union[str, Path],
        map_location: Optional[str] = "cpu",
    ) -> "MultimodalLateFusionModel":
        """Instantiate model from checkpoint."""
        ckpt = torch.load(path, map_location=map_location, weights_only=True)
        model = cls(
            image_embedding_dim=ckpt["image_embedding_dim"],
            tabular_embedding_dim=ckpt["tabular_embedding_dim"],
            fusion_dim=ckpt["fusion_dim"],
            pathology_classes=ckpt["pathology_classes"],
            fusion_strategy=ckpt.get("fusion_strategy", "gated"),
        )
        model.load_state_dict(ckpt["state_dict"])
        return model
