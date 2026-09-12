"""
MedFusion AI — Deep Learning Vision Backbones for Chest Radiographs.

Supports:
- DenseNet-121: Pre-trained feature extractor with 1024-dim dense representation and denseblock4 Grad-CAM hooks.
- EfficientNet-B0: Memory-efficient compound-scaled CNN backbone with 1280-dim feature representation.
- Modular embedding projection heads for multimodal fusion ingestion.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import torch
import torch.nn as nn
import torchvision.models as models


class BaseVisionBackbone(nn.Module, ABC):
    """Abstract base class for chest radiograph neural network backbones."""

    @abstractmethod
    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract global pooled embedding vector [batch_size, embedding_dim]."""
        pass

    @abstractmethod
    def get_last_conv_layer(self) -> nn.Module:
        """Return the final convolutional layer for Grad-CAM activation mapping."""
        pass

    def freeze(self, freeze: bool = True) -> None:
        """Freeze or unfreeze backbone parameters."""
        for param in self.parameters():
            param.requires_grad = not freeze


class DenseNet121Backbone(BaseVisionBackbone):
    """
    DenseNet-121 feature extractor optimized for thoracic radiograph pathology detection.
    Standard backbone recommended for NIH ChestX-ray14 and CheXpert benchmarks.
    """

    def __init__(
        self,
        pretrained: bool = False,
        embedding_dim: int = 512,
        dropout_rate: float = 0.3,
    ):
        super().__init__()
        weights = models.DenseNet121_Weights.DEFAULT if pretrained else None
        self.densenet = models.densenet121(weights=weights)
        self.raw_feature_dim = 1024

        # Remove default linear classifier
        del self.densenet.classifier

        # Global average pooling and adaptive projection head
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(p=dropout_rate)
        self.projection = nn.Sequential(
            nn.Linear(self.raw_feature_dim, embedding_dim),
            nn.BatchNorm1d(embedding_dim),
            nn.ReLU(inplace=True),
        )
        self.embedding_dim = embedding_dim

    def extract_raw_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract spatial feature map from DenseNet features block [batch_size, 1024, H, W]."""
        features = self.densenet.features(x)
        out = nn.functional.relu(features, inplace=False)
        return out

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract projected feature embedding [batch_size, embedding_dim]."""
        feat_map = self.extract_raw_features(x)
        pooled = self.pool(feat_map)
        flat = torch.flatten(pooled, 1)
        flat = self.dropout(flat)
        projected = self.projection(flat)
        return projected

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returns projected embedding."""
        return self.extract_features(x)

    def get_last_conv_layer(self) -> nn.Module:
        """Target layer for Grad-CAM explainability."""
        return self.densenet.features.norm5


class EfficientNetB0Backbone(BaseVisionBackbone):
    """
    EfficientNet-B0 feature extractor providing high parameter efficiency for resource-constrained inference.
    """

    def __init__(
        self,
        pretrained: bool = False,
        embedding_dim: int = 512,
        dropout_rate: float = 0.3,
    ):
        super().__init__()
        weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
        self.efficientnet = models.efficientnet_b0(weights=weights)
        self.raw_feature_dim = 1280

        # Remove default classifier
        del self.efficientnet.classifier

        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(p=dropout_rate)
        self.projection = nn.Sequential(
            nn.Linear(self.raw_feature_dim, embedding_dim),
            nn.BatchNorm1d(embedding_dim),
            nn.ReLU(inplace=True),
        )
        self.embedding_dim = embedding_dim

    def extract_raw_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract spatial feature map [batch_size, 1280, H, W]."""
        return self.efficientnet.features(x)

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract projected feature embedding [batch_size, embedding_dim]."""
        feat_map = self.extract_raw_features(x)
        pooled = self.pool(feat_map)
        flat = torch.flatten(pooled, 1)
        flat = self.dropout(flat)
        projected = self.projection(flat)
        return projected

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returns projected embedding."""
        return self.extract_features(x)

    def get_last_conv_layer(self) -> nn.Module:
        """Target layer for Grad-CAM explainability."""
        return self.efficientnet.features[-1]
