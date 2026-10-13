"""Typed report-preview contract with direct patient identifiers excluded."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.clinical_review import ReviewDecision
from app.models.diagnostic_case import CaseModality
from app.models.image_record import ImageType
from app.models.prediction_record import ConfidenceBand, ModelType, PredictionStatus


class ReportStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"


class ReportPatientSummary(BaseModel):
    """Minimal demographic summary; direct identifiers are intentionally omitted."""

    age: Optional[int] = None
    sex: str


class ReportImageInput(BaseModel):
    id: UUID
    image_type: ImageType
    mime_type: str
    sha256: str = Field(description="Digest identifying the exact uploaded image version")
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime


class ReportClinicalInput(BaseModel):
    id: UUID
    updated_at: datetime
    age_years: int
    sex_code: int
    chest_pain_type: int
    resting_bp_mm_hg: float
    cholesterol_mg_dl: float
    fasting_bs: int
    resting_ecg: int
    max_hr_bpm: float
    exercise_angina: int
    st_depression_mm: float
    st_slope: int
    num_major_vessels: int
    thalassemia: int
    bmi: Optional[float] = None
    smoking_status: Optional[str] = None


class ReportPredictionSummary(BaseModel):
    id: UUID
    model_type: ModelType
    model_version: str
    model_reported_finding: str
    raw_score: float = Field(ge=0.0, le=1.0)
    stored_probability: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_band: ConfidenceBand
    status: PredictionStatus
    abstention_reason: Optional[str] = None
    image_record_id: Optional[UUID] = None
    image_sha256: Optional[str] = None
    clinical_record_id: Optional[UUID] = None
    clinical_record_updated_at: Optional[datetime] = None
    input_version_current: bool
    explanation_id: Optional[UUID] = None
    explanation_type: Optional[str] = None
    created_at: datetime


class ReportReviewSummary(BaseModel):
    id: UUID
    prediction_id: UUID
    reviewer_id: UUID
    reviewer_role: Optional[str] = None
    decision: ReviewDecision
    modified_diagnosis: Optional[str] = None
    rationale: str
    reviewed_at: datetime


class CaseReportPreviewResponse(BaseModel):
    """Current persisted case snapshot; this preview is not a finalized report."""

    case_id: UUID
    case_reference: str
    generated_at: datetime
    status: ReportStatus
    modality: CaseModality
    patient: ReportPatientSummary
    image_input: Optional[ReportImageInput] = None
    clinical_input: Optional[ReportClinicalInput] = None
    prediction: Optional[ReportPredictionSummary] = None
    review: Optional[ReportReviewSummary] = None
    free_text_notes_included: bool = False
    probability_notice: str
    disclaimer: str
