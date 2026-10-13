"""Request and response contracts for stored model outputs.

Field names preserve the current API schema. They do not establish model validity,
calibration, clinical uncertainty, or a safety-validated abstention policy.
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
    confidence_band: str = Field(description="Reported model band; calibration and clinical meaning are not validated")
    calibrated_probability: Optional[float] = Field(None, ge=0.0, le=1.0)


class TabularRiskDetail(BaseModel):
    """Stored tabular model-output fields; not a validated clinical risk estimate."""

    model_config = ConfigDict(from_attributes=True)

    raw_probability: float = Field(ge=0.0, le=1.0, description="Raw uncalibrated risk probability")
    calibrated_probability: float = Field(ge=0.0, le=1.0, description="Stored output field; calibrator provenance and calibration are not verified")
    risk_tier: str = Field(description="Clinical risk tier (low, moderate, high, critical)")
    confidence_band: str = Field(description="Reported model band; calibration is not verified")
    positive: bool = Field(description="Flag indicating clinical risk threshold exceeded")


class ModalityGatingDetail(BaseModel):
    """Stored modality contribution fields; training provenance is not established."""

    model_config = ConfigDict(from_attributes=True)

    image_weight: float = Field(ge=0.0, le=1.0, description="Normalized visual modality gating weight")
    tabular_weight: float = Field(ge=0.0, le=1.0, description="Normalized tabular modality gating weight")
    dominant_modality: str = Field(description="Primary modality driving fusion decision")


class UncertaintyDetail(BaseModel):
    """Stored uncertainty-related model fields; thresholds are not clinically validated."""

    model_config = ConfigDict(from_attributes=True)

    entropy: float = Field(ge=0.0, description="Information entropy across predicted distributions")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Reported score; calibration and clinical meaning are not validated")
    confidence_band: str = Field(description="Confidence classification (high, moderate, low, abstain)")
    cross_modal_conflict: Optional[float] = Field(None, ge=0.0, le=1.0, description="Discordance between modalities")
    abstention_recommended: bool = Field(default=False, description="Stored model abstention flag; not a validated safety control")
    abstention_reasons: List[str] = Field(default_factory=list, description="Stored model-provided abstention reasons")


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
    generate_explainability: bool = Field(default=True, description="Request optional attribution artifacts when supported by an available model")
    selected_image_id: Optional[UUID] = Field(None, description="Specific image ID to evaluate; defaults to primary")
    selected_clinical_record_id: Optional[UUID] = Field(None, description="Specific clinical record to evaluate; defaults to latest")


class DirectPredictRequest(BaseModel):
    """Request payload for direct real-time inference without prior case persistence."""

    patient_mrn: Optional[str] = Field(None, description="Patient MRN (stored as an unkeyed SHA-256 digest; not de-identification)")
    tabular_features: Optional[Dict[str, Any]] = Field(None, description="Structured clinical parameters")
    generate_explainability: bool = Field(default=True, description="Request optional attribution artifacts when supported by an available model")
    model_version: Optional[str] = Field(None, description="Target model version")


class PredictionResponse(BaseModel):
    """Unified response payload emitted after AI case prediction."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: Optional[UUID] = None
    image_record_id: Optional[UUID] = Field(
        None, description="Image record used by this inference run"
    )
    clinical_record_id: Optional[UUID] = Field(
        None, description="Clinical record used by this inference run"
    )
    image_file_hash: Optional[str] = Field(
        None, description="SHA-256 of the image bytes used by this inference run"
    )
    clinical_record_updated_at: Optional[datetime] = Field(
        None, description="Version timestamp of the clinical record used"
    )
    model_type: ModelType
    model_version: str
    primary_condition: str
    raw_probability: float
    calibrated_probability: float = Field(
        description="Stored model output field; calibration is not verified"
    )
    confidence_score: float = Field(
        description="Reported score; calibration and clinical meaning are not validated"
    )
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
        "Engineering prototype without demonstrated clinical validation. Do not use to guide diagnosis, triage, or treatment."
    )
    created_at: datetime


class PredictionListResponse(BaseModel):
    """List container of prediction records."""

    total: int
    items: List[PredictionResponse]
