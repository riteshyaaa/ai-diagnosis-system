"""
MedFusion AI — Explainable AI (XAI) Record ORM Model.

Stores Grad-CAM visual heatmaps, SHAP feature importance attributions,
and textual summaries explaining the AI model predictions.
"""

import enum
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import Enum, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ExplanationType(str, enum.Enum):
    """Supported explanation mechanisms."""
    GRADCAM_SALIENCY = "gradcam_saliency"
    SHAP_FEATURE_IMPORTANCE = "shap_feature_importance"
    MULTIMODAL_ATTRIBUTION = "multimodal_attribution"


class ExplanationRecord(Base, UUIDMixin, TimestampMixin):
    """Explainability artifact associated with a prediction."""

    __tablename__ = "explanation_records"

    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prediction_records.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    explanation_type: Mapped[ExplanationType] = mapped_column(
        Enum(ExplanationType, name="explanation_type", create_type=True),
        nullable=False,
    )

    # Visual Explainability (Grad-CAM heatmap overlay file path)
    heatmap_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Relative path to stored Grad-CAM overlay image",
    )

    # Tabular Explainability (SHAP values map)
    shap_values: Mapped[Optional[Dict[str, float]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Dictionary mapping clinical feature names to SHAP values",
    )

    # Ranked key drivers for display
    top_features: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Ranked list of top contributing features with magnitude and direction",
    )

    # Clinical Interpretation Summary
    summary_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable text summarizing the key contributing factors",
    )

    # Relationships
    prediction: Mapped["PredictionRecord"] = relationship("PredictionRecord", back_populates="explanation")

    def __repr__(self) -> str:
        return f"<ExplanationRecord id={self.id} type='{self.explanation_type.value}'>"
