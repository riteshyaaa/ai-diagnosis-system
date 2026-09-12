"""
MedFusion AI — Clinical Record Pydantic Schemas.

Defines input/output schemas, validation rules, and physiological alert models
for structured tabular patient measurements (UCI Heart Disease feature set).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ml.datasets.heart_disease.constants import (
    ChestPainTypeEnum,
    ExerciseAnginaEnum,
    FastingBloodSugarEnum,
    PHYSIOLOGICAL_RANGES,
    RestingECGEnum,
    SexEnum,
    SmokingStatusEnum,
    STSlopeEnum,
    ThalassemiaEnum,
)


class ClinicalRecordBase(BaseModel):
    """Core 13 standard clinical parameters with type definitions and descriptions."""
    age: int = Field(..., ge=1, le=125, description="Patient age in years (1-125)")
    sex: int = Field(..., ge=0, le=1, description="Biological sex: 1 = Male, 0 = Female")
    chest_pain_type: int = Field(
        ...,
        ge=0,
        le=3,
        description="Chest pain type: 0 = Typical Angina, 1 = Atypical Angina, 2 = Non-anginal, 3 = Asymptomatic",
    )
    resting_bp: float = Field(
        ...,
        ge=50.0,
        le=260.0,
        description="Resting blood pressure in mm Hg (50 - 260)",
    )
    cholesterol: float = Field(
        ...,
        ge=80.0,
        le=600.0,
        description="Serum cholesterol in mg/dl (80 - 600)",
    )
    fasting_bs: int = Field(
        ...,
        ge=0,
        le=1,
        description="Fasting blood sugar > 120 mg/dl: 1 = True, 0 = False",
    )
    resting_ecg: int = Field(
        ...,
        ge=0,
        le=2,
        description="Resting ECG: 0 = Normal, 1 = ST-T abnormality, 2 = LV hypertrophy",
    )
    max_hr: float = Field(
        ...,
        ge=40.0,
        le=240.0,
        description="Maximum heart rate achieved (40 - 240 bpm)",
    )
    exercise_angina: int = Field(
        ...,
        ge=0,
        le=1,
        description="Exercise induced angina: 1 = Yes, 0 = No",
    )
    st_depression: float = Field(
        ...,
        ge=-2.0,
        le=8.0,
        description="ST depression induced by exercise relative to rest (oldpeak in mm)",
    )
    st_slope: int = Field(
        ...,
        ge=0,
        le=2,
        description="Slope of peak exercise ST segment: 0 = Upsloping, 1 = Flat, 2 = Downsloping",
    )
    num_major_vessels: int = Field(
        ...,
        ge=0,
        le=3,
        description="Number of major vessels (0-3) colored by fluoroscopy",
    )
    thalassemia: int = Field(
        ...,
        ge=1,
        le=3,
        description="Thalassemia status: 1 = Normal, 2 = Fixed defect, 3 = Reversible defect",
    )

    # Extended Parameters
    bmi: Optional[float] = Field(None, ge=10.0, le=75.0, description="Body Mass Index in kg/m²")
    smoking_status: Optional[str] = Field(
        None,
        description="Smoking history ('never', 'former', 'current')",
    )
    raw_metrics: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Supplementary laboratory findings or unmodeled metrics",
    )

    @field_validator("smoking_status")
    @classmethod
    def validate_smoking_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().lower()
            allowed = [e.value for e in SmokingStatusEnum]
            if clean not in allowed:
                raise ValueError(f"smoking_status must be one of {allowed}, got '{v}'")
            return clean
        return v


class ClinicalRecordCreate(ClinicalRecordBase):
    """Request payload for recording patient clinical tabular measurements."""
    pass


class ClinicalRecordUpdate(BaseModel):
    """Optional patch payload for updating clinical record in DRAFT state."""
    age: Optional[int] = Field(None, ge=1, le=125)
    sex: Optional[int] = Field(None, ge=0, le=1)
    chest_pain_type: Optional[int] = Field(None, ge=0, le=3)
    resting_bp: Optional[float] = Field(None, ge=50.0, le=260.0)
    cholesterol: Optional[float] = Field(None, ge=80.0, le=600.0)
    fasting_bs: Optional[int] = Field(None, ge=0, le=1)
    resting_ecg: Optional[int] = Field(None, ge=0, le=2)
    max_hr: Optional[float] = Field(None, ge=40.0, le=240.0)
    exercise_angina: Optional[int] = Field(None, ge=0, le=1)
    st_depression: Optional[float] = Field(None, ge=-2.0, le=8.0)
    st_slope: Optional[int] = Field(None, ge=0, le=2)
    num_major_vessels: Optional[int] = Field(None, ge=0, le=3)
    thalassemia: Optional[int] = Field(None, ge=1, le=3)
    bmi: Optional[float] = Field(None, ge=10.0, le=75.0)
    smoking_status: Optional[str] = None
    raw_metrics: Optional[Dict[str, Any]] = None


class ClinicalValidationReportSchema(BaseModel):
    """Structured report returned from clinical plausibility and safety checks."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    critical_alerts: List[str] = Field(default_factory=list)


class ClinicalRecordResponse(ClinicalRecordBase):
    """Full serialized clinical record model."""
    id: UUID
    case_id: UUID
    recorded_by_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalRecordWithValidationResponse(BaseModel):
    """Response returned upon recording measurements, including clinical validation flags."""
    record: ClinicalRecordResponse
    validation_report: ClinicalValidationReportSchema


class ClinicalRecordListResponse(BaseModel):
    """Paginated or listed collection of clinical records."""
    total: int
    items: List[ClinicalRecordResponse]
