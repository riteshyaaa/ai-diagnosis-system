"""Schemas for optional stored model-attribution artifacts.

These contracts do not imply that artifacts are available or clinically validated.
"""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.prediction import ModalityGatingDetail


CLINICAL_DISCLAIMER_TEXT = (
    "This is an engineering prototype without demonstrated clinical validation. Any stored attribution "
    "is a model-derived artifact, not a diagnosis, causal explanation, or verified disease localization."
)


class FeatureAttributionItem(BaseModel):
    """Detailed attribution for a single clinical feature."""

    model_config = ConfigDict(from_attributes=True)

    feature_name: str = Field(description="Raw clinical feature key (e.g. resting_bp, st_depression)")
    display_name: str = Field(description="Display label for the stored feature key; units may be unspecified")
    feature_value: Optional[Any] = Field(None, description="Patient's observed value")
    baseline_reference: Optional[str] = Field(None, description="Optional stored baseline label; not inferred from clinical guidance")
    shap_value: float = Field(description="Raw SHAP contribution value (log-odds / probability impact)")
    importance_rank: int = Field(ge=1, description="Rank ordered by absolute impact magnitude")
    direction: str = Field(description="'risk_increasing' if SHAP > 0, else 'risk_decreasing'")
    percentage_impact: float = Field(ge=0.0, le=100.0, description="Relative percentage contribution to total attribution")
    clinical_interpretation: Optional[str] = Field(None, description="Optional stored text; not a clinical interpretation")


class FeatureAttributionsResponse(BaseModel):
    """Comprehensive tabular feature attribution waterfall and breakdown."""

    model_config = ConfigDict(from_attributes=True)

    prediction_id: UUID
    case_id: Optional[UUID] = None
    model_type: str = Field(description="Model used for evaluation")
    base_value: float = Field(description="Stored attribution baseline; provenance and clinical meaning must be established separately")
    predicted_risk: float = Field(description="Stored model output probability; calibration is not validated by this service")
    total_features_evaluated: int = Field(ge=0)
    top_risk_increasing_features: List[FeatureAttributionItem] = Field(default_factory=list)
    top_risk_decreasing_features: List[FeatureAttributionItem] = Field(default_factory=list)
    all_features: List[FeatureAttributionItem] = Field(default_factory=list)
    summary_text: Optional[str] = None
    clinical_disclaimer: str = Field(default=CLINICAL_DISCLAIMER_TEXT)


class AttentionRegion(BaseModel):
    """Optional region associated with an attribution artifact; not a disease localization."""

    model_config = ConfigDict(from_attributes=True)

    box: List[float] = Field(
        description="Normalized bounding box coordinates [ymin, xmin, ymax, xmax] in range [0.0, 1.0]"
    )
    saliency_score: float = Field(ge=0.0, le=1.0, description="Mean saliency intensity in region")
    anatomical_region: Optional[str] = Field(None, description="Estimated thoracic anatomical zone")
    associated_pathology: Optional[str] = Field(None, description="Target condition evaluated")


class VisualExplanationResponse(BaseModel):
    """Optional visual-attribution artifact and related metadata."""

    model_config = ConfigDict(from_attributes=True)

    prediction_id: UUID
    case_id: Optional[UUID] = None
    target_pathology: str = Field(description="Thoracic condition evaluated (e.g. Cardiomegaly)")
    heatmap_url: Optional[str] = Field(None, description="API endpoint URL to download raw heatmap image")
    overlay_url: Optional[str] = Field(None, description="API endpoint URL to download overlaid radiograph image")
    overlay_base64: Optional[str] = Field(None, description="Base64 PNG string of overlay for instant UI rendering")
    heatmap_base64: Optional[str] = Field(None, description="Base64 PNG string of raw heatmap")
    attention_regions: List[AttentionRegion] = Field(default_factory=list)
    summary_text: Optional[str] = None
    clinical_disclaimer: str = Field(default=CLINICAL_DISCLAIMER_TEXT)


class ExplanationResponse(BaseModel):
    """Full composite XAI explanation response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prediction_id: UUID
    case_id: Optional[UUID] = None
    explanation_type: str = Field(description="gradcam_saliency, shap_feature_importance, multimodal_attribution")
    model_type: str
    primary_condition: str
    calibrated_probability: float
    confidence_band: str
    visual_explanation: Optional[VisualExplanationResponse] = None
    tabular_explanation: Optional[FeatureAttributionsResponse] = None
    modality_gating: Optional[ModalityGatingDetail] = None
    summary_text: Optional[str] = None
    clinical_disclaimer: str = Field(default=CLINICAL_DISCLAIMER_TEXT)
    created_at: datetime


class ExplanationListResponse(BaseModel):
    """Paginated or listed XAI explanation records."""

    model_config = ConfigDict(from_attributes=True)

    total: int
    items: List[ExplanationResponse]


class RecalculatePathologySaliencyRequest(BaseModel):
    """Request payload to recalculate Grad-CAM saliency for an alternative thoracic pathology."""

    target_pathology: str = Field(
        description="Target pathology name (Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass)"
    )
    target_layer: Optional[str] = Field(
        default=None,
        description="Optional CNN layer override (defaults to final convolutional layer)",
    )
