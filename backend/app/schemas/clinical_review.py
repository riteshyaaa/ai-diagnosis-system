"""
MedFusion AI — Clinical Review & Human-in-the-Loop Schemas.

Pydantic schemas for clinician review submission, validation,
concordance metrics, and audit responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.clinical_review import ReviewDecision

CLINICAL_DISCLAIMER_TEXT = (
    "MedFusion AI is an assistive Clinical Decision Support System (CDSS) and "
    "does not provide autonomous medical diagnosis. All diagnostic findings "
    "require licensed physician verification and clinical oversight."
)


class ReviewerSummary(BaseModel):
    """Compact summary of the reviewing clinician."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: str
    department: Optional[str] = None


class ClinicalReviewCreate(BaseModel):
    """Payload for submitting a human-in-the-loop clinical review."""
    prediction_id: Optional[UUID] = Field(
        default=None,
        description="Target AI prediction ID being evaluated. Required if not provided in URL.",
    )
    decision: ReviewDecision = Field(
        ...,
        description="Clinician verdict on AI findings: accept, modify, or reject.",
    )
    modified_diagnosis: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Corrected physician diagnosis. Required when decision is 'modify'.",
    )
    clinical_notes: str = Field(
        ...,
        min_length=5,
        max_length=4000,
        description="Mandatory physician notes explaining clinical reasoning and rationale.",
    )

    @model_validator(mode="after")
    def validate_modify_diagnosis(self) -> "ClinicalReviewCreate":
        if self.decision == ReviewDecision.MODIFY:
            if not self.modified_diagnosis or not self.modified_diagnosis.strip():
                raise ValueError("modified_diagnosis is mandatory when decision is 'modify'.")
        return self


class ClinicalReviewResponse(BaseModel):
    """Detailed response model for a clinical review record."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    prediction_id: UUID
    reviewer_id: UUID
    decision: ReviewDecision
    modified_diagnosis: Optional[str] = None
    clinical_notes: str
    reviewed_at: datetime
    created_at: datetime
    reviewer: Optional[ReviewerSummary] = None
    case_number: Optional[str] = None
    ai_predicted_diagnosis: Optional[str] = None
    concordance: Optional[bool] = None
    clinical_disclaimer: str = Field(
        default=CLINICAL_DISCLAIMER_TEXT,
        description="Mandatory regulatory CDSS notice",
    )


class ClinicalReviewListResponse(BaseModel):
    """Paginated collection of clinical review records."""
    total: int
    items: List[ClinicalReviewResponse]


class ClinicalReviewStatsResponse(BaseModel):
    """Aggregate analytics on human clinician reviews and AI concordance."""
    total_reviews: int
    accepted_count: int
    modified_count: int
    rejected_count: int
    concordance_rate: float = Field(
        description="Percentage of AI predictions accepted without modification (0.0 to 100.0)"
    )
    modification_rate: float = Field(
        description="Percentage of AI predictions modified by clinician (0.0 to 100.0)"
    )
    rejection_rate: float = Field(
        description="Percentage of AI predictions rejected by clinician (0.0 to 100.0)"
    )
    top_modified_diagnoses: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Frequency list of physician-corrected diagnostic findings",
    )
    recent_reviews: List[ClinicalReviewResponse] = Field(
        default_factory=list,
        description="Recent physician reviews",
    )
    clinical_disclaimer: str = Field(
        default=CLINICAL_DISCLAIMER_TEXT,
        description="Mandatory regulatory CDSS notice",
    )
