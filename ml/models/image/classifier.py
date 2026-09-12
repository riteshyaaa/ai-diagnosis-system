"""
MedFusion AI — Chest Radiograph Neural Network Classifier.

Full deep learning model combining CNN backbones with clinical diagnostic prediction heads,
temperature scaling for calibrated probability outputs, and multi-label pathology detection.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import torch
import torch.nn as nn

from ml.models.image.backbones import (
    BaseVisionBackbone,
    DenseNet121Backbone,
    EfficientNetB0Backbone,
)


class ChestXRayClassifier(nn.Module):
    """
    Multimodal-ready Chest Radiograph Deep Learning Classifier.
    Predicts multi-label thoracic pathologies and outputs calibrated embeddings.
    """

    DEFAULT_CLASSES = [
        "Atelectasis",
        "Cardiomegaly",
        "Effusion",
        "Infiltration",
        "Mass",
    ]

    def __init__(
        self,
        backbone_name: str = "densenet121",
        num_classes: Optional[int] = None,
        class_names: Optional[List[str]] = None,
        embedding_dim: int = 512,
        dropout_rate: float = 0.3,
        pretrained: bool = False,
        multi_label: bool = True,
        backbone: Optional[str] = None,
    ):
        super().__init__()
        self.class_names = class_names or self.DEFAULT_CLASSES
        self.num_classes = num_classes or len(self.class_names)
        self.embedding_dim = embedding_dim
        self.multi_label = multi_label
        chosen_backbone = backbone or backbone_name
        self.backbone_name = chosen_backbone.lower()

        # Instantiate selected backbone
        if self.backbone_name == "densenet121":
            self.backbone: BaseVisionBackbone = DenseNet121Backbone(
                pretrained=pretrained,
                embedding_dim=embedding_dim,
                dropout_rate=dropout_rate,
            )
        elif self.backbone_name == "efficientnet_b0":
            self.backbone = EfficientNetB0Backbone(
                pretrained=pretrained,
                embedding_dim=embedding_dim,
                dropout_rate=dropout_rate,
            )
        else:
            raise ValueError(
                f"Unsupported backbone '{chosen_backbone}'. Choose 'densenet121' or 'efficientnet_b0'."
            )

        # Classification head
        self.classifier = nn.Linear(embedding_dim, self.num_classes)

        # Learnable temperature scaling for probability calibration
        self.temperature = nn.Parameter(torch.ones(1))

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract global feature embedding [batch_size, embedding_dim]."""
        return self.backbone.extract_features(x)

    def get_last_conv_layer(self) -> nn.Module:
        """Target layer for Grad-CAM activation mapping."""
        return self.backbone.get_last_conv_layer()

    def forward(
        self,
        x: torch.Tensor,
        return_embeddings: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass.
        Args:
            x: Input radiograph tensor [batch_size, 3, 224, 224]
            return_embeddings: Whether to include intermediate embedding in output dictionary
        Returns:
            Dictionary containing 'logits', 'probabilities', and optional 'embeddings'
        """
        embeddings = self.extract_features(x)
        logits = self.classifier(embeddings)

        # Apply temperature scaling to logits
        temp = torch.clamp(self.temperature, min=0.01)
        scaled_logits = logits / temp

        if self.multi_label:
            probabilities = torch.sigmoid(scaled_logits)
        else:
            probabilities = torch.softmax(scaled_logits, dim=-1)

        result = {
            "logits": logits,
            "scaled_logits": scaled_logits,
            "probabilities": probabilities,
        }
        if return_embeddings:
            result["embeddings"] = embeddings

        return result

    def freeze_backbone(self) -> None:
        """Freeze backbone parameters for transfer learning / linear probing."""
        for param in self.backbone.parameters():
            param.requires_grad = False

    def unfreeze_backbone(self) -> None:
        """Unfreeze backbone parameters for end-to-end fine-tuning."""
        for param in self.backbone.parameters():
            param.requires_grad = True

    def predict(
        self,
        x: torch.Tensor,
        threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Inference helper converting tensor predictions to structured diagnostic predictions.
        """
        self.eval()
        with torch.no_grad():
            output = self.forward(x, return_embeddings=False)
            probs = output["probabilities"].cpu().numpy()

        results = []
        for batch_idx in range(probs.shape[0]):
            patient_probs = probs[batch_idx]
            findings = {}
            for class_idx, name in enumerate(self.class_names):
                p = float(patient_probs[class_idx])
                findings[name] = {
                    "probability": round(p, 4),
                    "present": p >= threshold,
                }
            results.append({
                "findings": findings,
                "max_risk_score": round(float(np.max(patient_probs)), 4) if len(patient_probs) > 0 else 0.0,
            })
        return results

    def save_checkpoint(self, path: Union[str, Path]) -> None:
        """Save model state dict and architecture metadata."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.state_dict(),
                "backbone_name": self.backbone_name,
                "num_classes": self.num_classes,
                "class_names": self.class_names,
                "embedding_dim": self.embedding_dim,
                "multi_label": self.multi_label,
            },
            dest,
        )

    @classmethod
    def load_checkpoint(
        cls,
        path: Union[str, Path],
        map_location: Optional[str] = "cpu",
    ) -> "ChestXRayClassifier":
        """Instantiate model from saved checkpoint."""
        checkpoint = torch.load(path, map_location=map_location, weights_only=True)
        model = cls(
            backbone_name=checkpoint["backbone_name"],
            num_classes=checkpoint["num_classes"],
            class_names=checkpoint["class_names"],
            embedding_dim=checkpoint["embedding_dim"],
            multi_label=checkpoint["multi_label"],
            pretrained=False,
        )
        model.load_state_dict(checkpoint["state_dict"])
        return model
