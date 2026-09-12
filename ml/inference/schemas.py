"""
MedFusion AI — ML Inference Schemas & Data Contracts.

Defines Pydantic models and Enums for unified multimodal AI inference requests,
diagnostic findings, risk tiering, uncertainty estimation, and explainability artifacts.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


class InferenceModality(str, Enum):
    """Inference input modality classification."""

    IMAGE_ONLY = "image_only"
    TABULAR_ONLY = "tabular_only"
    MULTIMODAL = "multimodal"


class ConfidenceBand(str, Enum):
    """Calibrated confidence bands."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    ABSTAIN = "abstain"


class RiskTier(str, Enum):
    """Cardiovascular clinical risk stratification."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class PathologyFinding(BaseModel):
    """Diagnostic prediction for an individual thoracic radiograph pathology."""

    model_config = ConfigDict(frozen=True)

    pathology: str
    probability: float
    threshold: float = 0.5
    positive: bool
    confidence_band: ConfidenceBand
    calibrated_probability: Optional[float] = None


class TabularRiskFinding(BaseModel):
    """Cardiovascular clinical risk prediction from structured EHR telemetry."""

    model_config = ConfigDict(frozen=True)

    raw_probability: float
    calibrated_probability: float
    risk_tier: RiskTier
    confidence_band: ConfidenceBand
    positive: bool


class ModalityGatingWeights(BaseModel):
    """Modality contribution weights learned during multimodal late fusion."""

    model_config = ConfigDict(frozen=True)

    image_weight: float
    tabular_weight: float
    dominant_modality: str


class UncertaintyEstimation(BaseModel):
    """Comprehensive uncertainty assessment and clinical safety abstention metrics."""

    model_config = ConfigDict(frozen=True)

    entropy: float
    confidence_score: float
    confidence_band: ConfidenceBand
    cross_modal_conflict: Optional[float] = None
    abstention_recommended: bool = False
    abstention_reasons: List[str] = Field(default_factory=list)


class ExplainabilitySummary(BaseModel):
    """XAI artifacts including Grad-CAM visual heatmaps and SHAP feature attributions."""

    model_config = ConfigDict(frozen=True)

    gradcam_heatmap_base64: Optional[str] = None
    gradcam_overlay_base64: Optional[str] = None
    gradcam_bounding_boxes: Optional[List[Dict[str, Any]]] = None
    shap_feature_contributions: Optional[List[Dict[str, Any]]] = None
    shap_base_value: Optional[float] = None


class InferenceRequest(BaseModel):
    """Unified request schema for clinical diagnosis and risk assessment."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    patient_mrn: Optional[str] = None
    image_path: Optional[str] = None
    image_bytes: Optional[bytes] = None
    tabular_features: Optional[Dict[str, Any]] = None
    generate_explainability: bool = True
    model_version: Optional[str] = None


class InferenceResponse(BaseModel):
    """Unified response payload emitted by MedFusion AI inference pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    inference_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str
    modality: InferenceModality
    patient_mrn_hash: Optional[str] = None
    pathology_findings: List[PathologyFinding] = Field(default_factory=list)
    clinical_risk: Optional[TabularRiskFinding] = None
    modality_gating: Optional[ModalityGatingWeights] = None
    uncertainty: UncertaintyEstimation
    explainability: Optional[ExplainabilitySummary] = None
    model_metadata: Dict[str, Any] = Field(default_factory=dict)
    clinical_disclaimer: str = (
        "MedFusion AI is an assistive Clinical Decision Support System (CDSS) for licensed "
        "healthcare professionals. It does not provide autonomous medical diagnosis. "
        "All predictions require human-in-the-loop clinical review and validation."
    )
