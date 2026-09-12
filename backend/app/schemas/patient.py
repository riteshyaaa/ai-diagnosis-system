"""
MedFusion AI — Patient Pydantic Schemas.

Provides validation schemas for de-identified patient data ingestion,
demographic filtering, updates, and privacy-preserving responses.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.patient import BiologicalSex


class PatientBase(BaseModel):
    """Base demographic attributes for patient records."""
    age: Optional[int] = Field(
        None,
        ge=0,
        le=125,
        description="Patient age in years (0-125)",
        examples=[58],
    )
    sex: BiologicalSex = Field(
        default=BiologicalSex.UNKNOWN,
        description="Biological sex for clinical stratification",
        examples=[BiologicalSex.FEMALE],
    )
    blood_group: Optional[str] = Field(
        None,
        max_length=10,
        description="Blood group (e.g. A+, O-, B+)",
        examples=["O+"],
    )
    medical_history_summary: Optional[str] = Field(
        None,
        max_length=5000,
        description="Anonymized clinical summary of previous diagnoses, risk factors, or history",
        examples=["Hypertension for 8 years, former smoker, family history of CAD."],
    )


class PatientCreate(PatientBase):
    """Schema for registering a new de-identified patient."""
    mrn: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        description="Raw Medical Record Number (will be SHA-256 hashed immediately; raw string is NEVER persisted)",
        examples=["MRN-2026-998811"],
    )
    mrn_hash: Optional[str] = Field(
        None,
        min_length=64,
        max_length=64,
        description="Pre-computed 64-character hex SHA-256 MRN hash (alternative to raw mrn)",
        examples=["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    )


class PatientUpdate(BaseModel):
    """Schema for updating demographic and medical history attributes."""
    age: Optional[int] = Field(
        None,
        ge=0,
        le=125,
        description="Patient age in years (0-125)",
    )
    sex: Optional[BiologicalSex] = Field(
        None,
        description="Biological sex",
    )
    blood_group: Optional[str] = Field(
        None,
        max_length=10,
        description="Blood group",
    )
    medical_history_summary: Optional[str] = Field(
        None,
        max_length=5000,
        description="Anonymized medical history summary",
    )


class PatientResponse(PatientBase):
    """Schema for de-identified patient details in API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mrn_hash: str = Field(
        description="SHA-256 cryptographic hash of the patient MRN",
    )
    created_at: datetime
    updated_at: datetime


class PatientListResponse(BaseModel):
    """Paginated list of patients."""
    total: int
    items: List[PatientResponse]
    skip: int
    limit: int
