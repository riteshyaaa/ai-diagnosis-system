"""
MedFusion AI — Diagnostic Case Pydantic Schemas.

Provides validation schemas for diagnostic case creation, lifecycle transitions,
demographic filtering, multi-modal linkages, and full relational graph responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.diagnostic_case import CaseModality, CaseStatus
from app.models.image_record import ImageType
from app.models.prediction_record import ConfidenceBand, ModelType, PredictionStatus
from app.models.clinical_review import ReviewDecision
from app.schemas.patient import PatientResponse


# --- Subordinate Entity Summary Schemas ---

class ImageRecordSummary(BaseModel):
    """Compact summary of an associated medical radiograph."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    image_type: ImageType
    original_filename: str
    file_path: str
    file_size_bytes: int
    file_hash: str
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime


class ClinicalRecordSummary(BaseModel):
    """Compact summary of associated structured clinical tabular parameters."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    age: Optional[int] = None
    sex: Optional[int] = None
    chest_pain_type: Optional[int] = None
    resting_bp: Optional[float] = None
    cholesterol: Optional[float] = None
    fasting_bs: Optional[int] = None
    resting_ecg: Optional[int] = None
    max_hr: Optional[float] = None
    exercise_angina: Optional[int] = None
    st_depression: Optional[float] = None
    st_slope: Optional[int] = None
    num_major_vessels: Optional[int] = None
    thalassemia: Optional[int] = None
    created_at: datetime


class ExplanationSummary(BaseModel):
    """Compact summary of XAI visual heatmap or feature attributions."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    explanation_type: str
    heatmap_path: Optional[str] = None
    shap_values: Optional[Dict[str, Any]] = None
    top_features: Optional[List[Dict[str, Any]]] = None
    summary_text: Optional[str] = None
    created_at: datetime


class PredictionSummary(BaseModel):
    """Compact summary of an AI inference result and uncertainty metrics."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_type: ModelType
    model_version: str
    primary_condition: str
    raw_probability: float
    calibrated_probability: float
    confidence_score: float
    confidence_band: ConfidenceBand
    status: PredictionStatus
    detailed_predictions: Optional[Dict[str, float]] = None
    inference_latency_ms: Optional[float] = None
    explanation: Optional[ExplanationSummary] = None
    created_at: datetime


class ReviewSummary(BaseModel):
    """Compact summary of human-in-the-loop clinician review decisions."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reviewer_id: UUID
    decision: ReviewDecision
    modified_diagnosis: Optional[str] = None
    clinical_notes: str
    reviewed_at: datetime


# --- Diagnostic Case Core Schemas ---

class CaseBase(BaseModel):
    """Base fields for a diagnostic case."""
    modality: CaseModality = Field(
        default=CaseModality.MULTIMODAL,
        description="Diagnostic evaluation modality (image_only, tabular_only, or multimodal)",
    )
    chief_complaint: Optional[str] = Field(
        None,
        max_length=500,
        description="Patient's primary presenting symptoms or clinical question",
        examples=["Acute retrosternal chest pressure radiating to left arm with exertional dyspnea."],
    )
    clinical_notes: Optional[str] = Field(
        None,
        description="Additional clinical background, physical exam notes, or clinician observations",
        examples=["Patient has history of uncontrolled hypertension and dyslipidemia."],
    )


class CaseCreate(CaseBase):
    """Schema for instantiating a new diagnostic case."""
    patient_id: UUID = Field(
        description="UUID of the de-identified patient record",
    )
    case_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Optional custom case number; auto-generated if omitted (e.g. CASE-2026-XXXXX)",
    )


class CaseUpdate(BaseModel):
    """Schema for updating clinical notes or case modality in DRAFT state."""
    modality: Optional[CaseModality] = None
    chief_complaint: Optional[str] = Field(None, max_length=500)
    clinical_notes: Optional[str] = None


class CaseStatusUpdate(BaseModel):
    """Schema for advancing or altering the workflow status of a case."""
    status: CaseStatus = Field(
        description="Target lifecycle status (e.g. SUBMITTED, PROCESSING, COMPLETED, REVIEWED, ARCHIVED)",
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional justification or context for manual state transition",
    )


class CaseResponse(CaseBase):
    """Standard diagnostic case response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    patient_id: UUID
    created_by_id: UUID
    status: CaseStatus
    created_at: datetime
    updated_at: datetime


class CaseDetailResponse(CaseResponse):
    """Comprehensive diagnostic case response including complete relational graph."""
    patient: Optional[PatientResponse] = None
    images: List[ImageRecordSummary] = []
    clinical_records: List[ClinicalRecordSummary] = []
    predictions: List[PredictionSummary] = []
    reviews: List[ReviewSummary] = []


class CaseListResponse(BaseModel):
    """Paginated list of diagnostic cases."""
    total: int
    items: List[CaseResponse]
    skip: int
    limit: int
