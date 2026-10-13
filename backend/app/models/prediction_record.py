"""
MedFusion AI — AI Prediction Record ORM Model.

Stores prediction records and model-output fields. Calibration, confidence, uncertainty,
and abstention semantics depend on separately verified artifacts and evaluation.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.clinical_review import ClinicalReview
    from app.models.diagnostic_case import DiagnosticCase
    from app.models.explanation_record import ExplanationRecord


class ModelType(str, enum.Enum):
    """Supported machine learning model architectures."""
    IMAGE_DENSENET121 = "image_densenet121"
    IMAGE_EFFICIENTNET_B0 = "image_efficientnet_b0"
    VISION_CLASSIFIER = "vision_classifier"
    TABULAR_MLP = "tabular_mlp"
    TABULAR_XGBOOST = "tabular_xgboost"
    TABULAR_LOGISTIC_REGRESSION = "tabular_logistic_regression"
    TABULAR_RANDOM_FOREST = "tabular_random_forest"
    MULTIMODAL_FUSION = "multimodal_fusion"


class ConfidenceBand(str, enum.Enum):
    """Uncertainty quantification confidence categories."""
    HIGH = "high"          # >= 0.85
    MODERATE = "moderate"  # 0.60 - 0.84
    LOW = "low"            # < 0.60 (Triggers abstention recommendation)
    ABSTAIN = "abstain"    # Abstention required due to high uncertainty or degraded quality


class PredictionStatus(str, enum.Enum):
    """Clinical safety status of the AI prediction."""
    CONFIDENT = "confident"
    UNCERTAIN = "uncertain"
    ABSTAINED = "abstained"


class PredictionRecord(Base, UUIDMixin, TimestampMixin):
    """AI inference prediction result entity."""

    __tablename__ = "prediction_records"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("image_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    clinical_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinical_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    image_file_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of the image bytes used by this inference run",
    )
    clinical_record_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Clinical record version timestamp used by this inference run",
    )
    model_type: Mapped[ModelType] = mapped_column(
        Enum(ModelType, name="model_type", create_type=True),
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Semantic version or hash of the model artifact used",
    )
    primary_condition: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Primary target disease or pathology evaluated",
    )

    # Probabilities & Confidence
    raw_probability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Uncalibrated model output score (0.0 to 1.0)",
    )
    calibrated_probability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Temperature-scaled or isotonic-calibrated probability (0.0 to 1.0)",
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Normalized model confidence score (0.0 to 1.0)",
    )
    confidence_band: Mapped[ConfidenceBand] = mapped_column(
        Enum(ConfidenceBand, name="confidence_band", create_type=True),
        nullable=False,
        index=True,
    )
    status: Mapped[PredictionStatus] = mapped_column(
        Enum(PredictionStatus, name="prediction_status", create_type=True),
        default=PredictionStatus.CONFIDENT,
        nullable=False,
    )
    abstention_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Rationale if model abstained from making an assertion",
    )

    # Multi-label class distribution / detailed scores
    detailed_predictions: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Dictionary of all predicted classes and their calibrated probabilities",
    )

    # Performance metric
    inference_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Wall-clock inference time in milliseconds",
    )

    # Relationships
    case: Mapped["DiagnosticCase"] = relationship("DiagnosticCase", back_populates="predictions")
    explanation: Mapped[Optional["ExplanationRecord"]] = relationship(
        "ExplanationRecord",
        back_populates="prediction",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reviews: Mapped[List["ClinicalReview"]] = relationship(
        "ClinicalReview",
        back_populates="prediction",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<PredictionRecord id={self.id} model='{self.model_type.value}' "
            f"condition='{self.primary_condition}' prob={self.calibrated_probability:.3f}>"
        )
