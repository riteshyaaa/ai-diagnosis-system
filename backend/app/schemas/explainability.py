"""
MedFusion AI — Explainability (XAI) Pydantic Schemas.

Defines comprehensive request and response contracts for:
- Grad-CAM visual saliency heatmaps and bounding attention regions
- Tabular SHAP feature attribution waterfall and impact analysis
- Multimodal attribution fusing radiograph visual cues and clinical parameters
- On-demand pathology saliency recalculation
- Mandatory non-autonomous CDSS regulatory disclaimers
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.prediction import ModalityGatingDetail


CLINICAL_DISCLAIMER_TEXT = (
    "MedFusion AI is an assistive Clinical Decision Support System (CDSS) and does not provide "
    "autonomous medical diagnosis. Visual saliency heatmaps, attention regions, and SHAP feature "
    "attributions indicate statistical model correlations and must be reviewed and verified by "
    "a qualified, licensed healthcare professional in conjunction with full patient clinical history."
)


class FeatureAttributionItem(BaseModel):
    """Detailed attribution for a single clinical feature."""

    model_config = ConfigDict(from_attributes=True)

    feature_name: str = Field(description="Raw clinical feature key (e.g. resting_bp, st_depression)")
    display_name: str = Field(description="Clinician-friendly feature name with units")
    feature_value: Optional[Any] = Field(None, description="Patient's observed value")
    baseline_reference: Optional[str] = Field(None, description="Standard clinical reference range")
    shap_value: float = Field(description="Raw SHAP contribution value (log-odds / probability impact)")
    importance_rank: int = Field(ge=1, description="Rank ordered by absolute impact magnitude")
    direction: str = Field(description="'risk_increasing' if SHAP > 0, else 'risk_decreasing'")
    percentage_impact: float = Field(ge=0.0, le=100.0, description="Relative percentage contribution to total attribution")
    clinical_interpretation: Optional[str] = Field(None, description="Contextual interpretation of feature contribution")


class FeatureAttributionsResponse(BaseModel):
    """Comprehensive tabular feature attribution waterfall and breakdown."""

    model_config = ConfigDict(from_attributes=True)

    prediction_id: UUID
    case_id: Optional[UUID] = None
    model_type: str = Field(description="Model used for evaluation")
    base_value: float = Field(description="Baseline expected probability across population")
    predicted_risk: float = Field(description="Final calibrated probability for the patient")
    total_features_evaluated: int = Field(ge=0)
    top_risk_increasing_features: List[FeatureAttributionItem] = Field(default_factory=list)
    top_risk_decreasing_features: List[FeatureAttributionItem] = Field(default_factory=list)
    all_features: List[FeatureAttributionItem] = Field(default_factory=list)
    summary_text: Optional[str] = None
    clinical_disclaimer: str = Field(default=CLINICAL_DISCLAIMER_TEXT)


class AttentionRegion(BaseModel):
    """High-attention anatomical or pathological bounding box derived from Grad-CAM saliency."""

    model_config = ConfigDict(from_attributes=True)

    box: List[float] = Field(
        description="Normalized bounding box coordinates [ymin, xmin, ymax, xmax] in range [0.0, 1.0]"
    )
    saliency_score: float = Field(ge=0.0, le=1.0, description="Mean saliency intensity in region")
    anatomical_region: Optional[str] = Field(None, description="Estimated thoracic anatomical zone")
    associated_pathology: Optional[str] = Field(None, description="Target condition evaluated")


class VisualExplanationResponse(BaseModel):
    """Visual Grad-CAM saliency map and attention metadata."""

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
