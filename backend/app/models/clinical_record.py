"""
MedFusion AI — Clinical Record ORM Model.

Stores structured tabular clinical measurements (vitals, laboratory findings,
cardiovascular risk indicators) matching UCI Heart Disease / clinical parameters.
"""

from typing import Any, Dict, Optional
import uuid
from sqlalchemy import Float, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ClinicalRecord(Base, UUIDMixin, TimestampMixin):
    """Structured clinical tabular data entity."""

    __tablename__ = "clinical_records"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Core Clinical Features (UCI Heart Disease feature set)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[int] = mapped_column(Integer, nullable=False, comment="1 = male, 0 = female")
    chest_pain_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0 = typical angina, 1 = atypical, 2 = non-anginal, 3 = asymptomatic"
    )
    resting_bp: Mapped[float] = mapped_column(Float, nullable=False, comment="Resting blood pressure in mm Hg")
    cholesterol: Mapped[float] = mapped_column(Float, nullable=False, comment="Serum cholesterol in mg/dl")
    fasting_bs: Mapped[int] = mapped_column(Integer, nullable=False, comment="1 if > 120 mg/dl, 0 otherwise")
    resting_ecg: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0 = normal, 1 = ST-T wave abnormality, 2 = left ventricular hypertrophy"
    )
    max_hr: Mapped[float] = mapped_column(Float, nullable=False, comment="Maximum heart rate achieved")
    exercise_angina: Mapped[int] = mapped_column(Integer, nullable=False, comment="1 = yes, 0 = no")
    st_depression: Mapped[float] = mapped_column(Float, nullable=False, comment="ST depression induced by exercise (oldpeak)")
    st_slope: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0 = upsloping, 1 = flat, 2 = downsloping"
    )
    num_major_vessels: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Number of major vessels (0-3) colored by flourosopy"
    )
    thalassemia: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="1 = normal, 2 = fixed defect, 3 = reversible defect"
    )

    # Extended Clinical Parameters
    bmi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    smoking_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Semi-structured extended measurements
    raw_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Flexible JSON storage for supplementary lab values or vitals",
    )

    # Relationships
    case: Mapped["DiagnosticCase"] = relationship("DiagnosticCase", back_populates="clinical_records")
    recorder: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<ClinicalRecord id={self.id} case_id={self.case_id} age={self.age}>"
