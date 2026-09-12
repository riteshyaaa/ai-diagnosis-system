"""
MedFusion AI — AI Prediction & Inference Pydantic Schemas.

Defines request and response data contracts for:
- Case-triggered multimodal/unimodal AI inference
- Real-time standalone inference evaluation
- Diagnostic multi-pathology probabilities and confidence bands
- Calibrated cardiovascular risk predictions
- Modality fusion gating weights
- Clinical uncertainty quantification & safety abstention
- Explainability artifact references (Grad-CAM heatmaps, SHAP contributions)
- Non-autonomous CDSS regulatory disclaimers
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.prediction_record import ConfidenceBand, ModelType, PredictionStatus


class PathologyDetail(BaseModel):
    """Prediction detail for an individual thoracic radiograph pathology."""

    model_config = ConfigDict(from_attributes=True)

    pathology: str = Field(description="Thoracic condition name (e.g. Cardiomegaly, Atelectasis)")
    probability: float = Field(ge=0.0, le=1.0, description="Model prediction probability")
    threshold: float = Field(default=0.5, description="Decision threshold applied")
    positive: bool = Field(description="Flag indicating if probability exceeds decision threshold")
    confidence_band: str = Field(description="Calibrated confidence band (high, moderate, low, abstain)")
    calibrated_probability: Optional[float] = Field(None, ge=0.0, le=1.0)


class TabularRiskDetail(BaseModel):
    """Clinical risk prediction detail derived from structured EHR telemetry."""

    model_config = ConfigDict(from_attributes=True)

    raw_probability: float = Field(ge=0.0, le=1.0, description="Raw uncalibrated risk probability")
    calibrated_probability: float = Field(ge=0.0, le=1.0, description="Isotonic/Platt calibrated risk probability")
    risk_tier: str = Field(description="Clinical risk tier (low, moderate, high, critical)")
    confidence_band: str = Field(description="Calibrated confidence band")
    positive: bool = Field(description="Flag indicating clinical risk threshold exceeded")


class ModalityGatingDetail(BaseModel):
    """Modality contribution weights learned during multimodal late fusion."""

    model_config = ConfigDict(from_attributes=True)

    image_weight: float = Field(ge=0.0, le=1.0, description="Normalized visual modality gating weight")
    tabular_weight: float = Field(ge=0.0, le=1.0, description="Normalized tabular modality gating weight")
    dominant_modality: str = Field(description="Primary modality driving fusion decision")


class UncertaintyDetail(BaseModel):
    """Comprehensive uncertainty assessment and clinical safety abstention metrics."""

    model_config = ConfigDict(from_attributes=True)

    entropy: float = Field(ge=0.0, description="Information entropy across predicted distributions")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Overall calibrated confidence score")
    confidence_band: str = Field(description="Confidence classification (high, moderate, low, abstain)")
    cross_modal_conflict: Optional[float] = Field(None, ge=0.0, le=1.0, description="Discordance between modalities")
    abstention_recommended: bool = Field(default=False, description="Flag indicating model abstention from asserting diagnosis")
    abstention_reasons: List[str] = Field(default_factory=list, description="Clinical safety reasons for abstention")


class ExplainabilityDetail(BaseModel):
    """Explainability artifacts and interpretation summaries."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[UUID] = None
    explanation_type: str = Field(description="Mechanism: gradcam_saliency, shap_feature_importance, multimodal_attribution")
    heatmap_path: Optional[str] = Field(None, description="Storage path or endpoint URL to Grad-CAM heatmap")
    heatmap_base64: Optional[str] = Field(None, description="Base64 encoded Grad-CAM heatmap image")
    overlay_base64: Optional[str] = Field(None, description="Base64 encoded Grad-CAM overlay on original image")
    shap_values: Optional[Dict[str, float]] = Field(None, description="Raw SHAP feature contribution values")
    top_features: Optional[List[Dict[str, Any]]] = Field(None, description="Ranked key clinical feature drivers")
    summary_text: Optional[str] = Field(None, description="Human-readable clinical rationale summary")


class CasePredictRequest(BaseModel):
    """Request payload to trigger AI inference on an existing diagnostic case."""

    model_version: Optional[str] = Field(None, description="Target model version (e.g. 1.0.0); defaults to active")
    generate_explainability: bool = Field(default=True, description="Whether to compute Grad-CAM and SHAP artifacts")
    selected_image_id: Optional[UUID] = Field(None, description="Specific image ID to evaluate; defaults to primary")
    selected_clinical_record_id: Optional[UUID] = Field(None, description="Specific clinical record to evaluate; defaults to latest")


class DirectPredictRequest(BaseModel):
    """Request payload for direct real-time inference without prior case persistence."""

    patient_mrn: Optional[str] = Field(None, description="Patient MRN (automatically hashed with SHA-256)")
    tabular_features: Optional[Dict[str, Any]] = Field(None, description="Structured clinical parameters")
    generate_explainability: bool = Field(default=True, description="Whether to compute Grad-CAM and SHAP artifacts")
    model_version: Optional[str] = Field(None, description="Target model version")


class PredictionResponse(BaseModel):
    """Unified response payload emitted after AI case prediction."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: Optional[UUID] = None
    model_type: ModelType
    model_version: str
    primary_condition: str
    raw_probability: float
    calibrated_probability: float
    confidence_score: float
    confidence_band: ConfidenceBand
    status: PredictionStatus
    abstention_reason: Optional[str] = None
    detailed_predictions: Dict[str, Any] = Field(default_factory=dict)
    pathology_findings: List[PathologyDetail] = Field(default_factory=list)
    clinical_risk: Optional[TabularRiskDetail] = None
    modality_gating: Optional[ModalityGatingDetail] = None
    uncertainty: UncertaintyDetail
    inference_latency_ms: float
    explanation: Optional[ExplainabilityDetail] = None
    clinical_disclaimer: str = (
        "MedFusion AI is an assistive Clinical Decision Support System (CDSS) for licensed "
        "healthcare professionals. It does not provide autonomous medical diagnosis. "
        "All predictions require human-in-the-loop clinical review and validation."
    )
    created_at: datetime


class PredictionListResponse(BaseModel):
    """List container of prediction records."""

    total: int
    items: List[PredictionResponse]
