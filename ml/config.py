"""
MedFusion AI — ML Configuration.

Centralized configuration for ML pipelines. Training hyperparameters,
dataset paths, model architecture settings, and evaluation parameters
are defined here to ensure reproducibility.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# Project root (two levels up from ml/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODEL_DIR = PROJECT_ROOT / "models" / "registry"
EXPERIMENT_DIR = PROJECT_ROOT / "ml" / "experiments"


@dataclass
class ImageModelConfig:
    """Configuration for chest X-ray image classification."""

    # Dataset
    dataset_name: str = "nih_chest_xray"
    image_size: int = 224
    num_channels: int = 3

    # Classes (NIH ChestX-ray14 — initial 5 most prevalent)
    target_classes: List[str] = field(
        default_factory=lambda: [
            "Atelectasis",
            "Cardiomegaly",
            "Effusion",
            "Infiltration",
            "Mass",
        ]
    )

    # Training
    batch_size: int = 32
    num_epochs: int = 50
    learning_rate: float = 1e-4
    weight_decay: float = 1e-5
    patience: int = 5  # Early stopping patience (validation AUC)
    early_stopping_patience: int = 5

    # Augmentation
    horizontal_flip_prob: float = 0.5
    rotation_limit: int = 15
    brightness_limit: float = 0.2
    contrast_limit: float = 0.2

    # Model
    backbone: str = "densenet121"  # densenet121, efficientnet_b0
    pretrained: bool = True
    dropout_rate: float = 0.3

    # Normalization (ImageNet stats)
    mean: List[float] = field(default_factory=lambda: [0.485, 0.456, 0.406])
    std: List[float] = field(default_factory=lambda: [0.229, 0.224, 0.225])

    # Split ratios
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    random_seed: int = 42

    def __post_init__(self):
        if self.early_stopping_patience != 5 and self.patience == 5:
            self.patience = self.early_stopping_patience
        elif self.patience != 5 and self.early_stopping_patience == 5:
            self.early_stopping_patience = self.patience


@dataclass
class TabularModelConfig:
    """Configuration for clinical risk prediction from tabular data."""

    # Dataset
    dataset_name: str = "uci_heart_disease"

    # Neural & Tree Training
    batch_size: int = 32
    num_epochs: int = 50
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    patience: int = 5
    early_stopping_patience: int = 5
    hidden_dims: List[int] = field(default_factory=lambda: [128, 64])

    # Splits & CV
    test_size: float = 0.15
    val_size: float = 0.15
    random_seed: int = 42
    cv_folds: int = 5

    # XGBoost / Tree defaults (can be tuned via Optuna)
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.1
    xgb_n_estimators: int = 200
    xgb_subsample: float = 0.8
    xgb_colsample_bytree: float = 0.8

    # Calibration
    calibration_method: str = "isotonic"  # isotonic, platt

    def __post_init__(self):
        if self.early_stopping_patience != 5 and self.patience == 5:
            self.patience = self.early_stopping_patience
        elif self.patience != 5 and self.early_stopping_patience == 5:
            self.early_stopping_patience = self.patience


@dataclass
class FusionModelConfig:
    """Configuration for multimodal late-fusion model."""

    # Embedding dimensions
    image_embedding_dim: int = 512
    clinical_embedding_dim: int = 128
    fusion_hidden_dim: int = 256

    # Training
    batch_size: int = 16
    num_epochs: int = 30
    learning_rate: float = 5e-5
    weight_decay: float = 1e-4
    dropout_rate: float = 0.4
    random_seed: int = 42
    patience: int = 5
    early_stopping_patience: int = 5
    pathology_weight: float = 1.0
    risk_weight: float = 1.0
    fusion_strategy: str = "gated"

    # Encoder freezing strategy
    freeze_image_encoder: bool = True
    freeze_tabular_encoder: bool = True
    fine_tune_after_epoch: int = 10  # Unfreeze after this epoch

    def __post_init__(self):
        if self.early_stopping_patience != 5 and self.patience == 5:
            self.patience = self.early_stopping_patience
        elif self.patience != 5 and self.early_stopping_patience == 5:
            self.early_stopping_patience = self.patience


@dataclass
class ExplainabilityConfig:
    """Configuration for XAI modules."""

    # Grad-CAM
    gradcam_target_layer: str = "features.denseblock4"  # DenseNet-121
    gradcam_colormap: str = "jet"
    gradcam_alpha: float = 0.4  # Overlay opacity

    # SHAP
    shap_max_samples: int = 100  # Background samples for KernelExplainer
    shap_top_features: int = 10  # Top features to display


@dataclass
class ConfidenceConfig:
    """Configuration for uncertainty and confidence estimation."""

    # Temperature scaling (learned on validation set)
    initial_temperature: float = 1.5

    # Confidence bands (thresholds derived from validation experiments)
    high_confidence_threshold: float = 0.85
    moderate_confidence_threshold: float = 0.60
    # Below moderate → low confidence → abstention

    # Abstention
    abstention_message: str = (
        "Low-confidence prediction — clinician review required."
    )
