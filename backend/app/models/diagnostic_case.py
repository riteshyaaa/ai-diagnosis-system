"""
MedFusion AI — Diagnostic Case ORM Model.

Top-level diagnostic session linking a patient, uploaded multimodal inputs
(images and tabular records), AI predictions, and human clinician reviews.
"""

import enum
from typing import List, Optional
import uuid
from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class CaseModality(str, enum.Enum):
    """Input modality types for diagnostic evaluation."""
    IMAGE_ONLY = "image_only"
    TABULAR_ONLY = "tabular_only"
    MULTIMODAL = "multimodal"


class CaseStatus(str, enum.Enum):
    """Lifecycle status of a diagnostic case."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


class DiagnosticCase(Base, UUIDMixin, TimestampMixin):
    """Diagnostic case entity container."""

    __tablename__ = "diagnostic_cases"

    case_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    modality: Mapped[CaseModality] = mapped_column(
        Enum(CaseModality, name="case_modality", create_type=True),
        default=CaseModality.MULTIMODAL,
        nullable=False,
    )
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status", create_type=True),
        default=CaseStatus.DRAFT,
        nullable=False,
        index=True,
    )
    chief_complaint: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    clinical_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="cases")
    creator: Mapped["User"] = relationship("User")
    images: Mapped[List["ImageRecord"]] = relationship(
        "ImageRecord",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    clinical_records: Mapped[List["ClinicalRecord"]] = relationship(
        "ClinicalRecord",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    predictions: Mapped[List["PredictionRecord"]] = relationship(
        "PredictionRecord",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="desc(PredictionRecord.created_at)",
    )
    reviews: Mapped[List["ClinicalReview"]] = relationship(
        "ClinicalReview",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="desc(ClinicalReview.reviewed_at)",
    )

    def __repr__(self) -> str:
        return f"<DiagnosticCase id={self.id} case_number='{self.case_number}' status='{self.status.value}'>"
