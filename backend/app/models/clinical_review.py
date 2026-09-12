"""
MedFusion AI — Human-in-the-Loop Clinical Review ORM Model.

Enforces human doctor supervision: clinicians review AI findings and
record decisions (Accept, Modify, Reject) with mandatory rationale.
"""

from datetime import datetime, timezone
import enum
from typing import Optional
import uuid
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ReviewDecision(str, enum.Enum):
    """Clinician verdict on the AI diagnostic output."""
    ACCEPT = "accept"
    MODIFY = "modify"
    REJECT = "reject"


class ClinicalReview(Base, UUIDMixin, TimestampMixin):
    """Clinical review audit entity."""

    __tablename__ = "clinical_reviews"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prediction_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, name="review_decision", create_type=True),
        nullable=False,
        index=True,
    )
    modified_diagnosis: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Required if decision is MODIFY: clinician's corrected diagnosis",
    )
    clinical_notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Mandatory physician notes explaining clinical reasoning",
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    case: Mapped["DiagnosticCase"] = relationship("DiagnosticCase", back_populates="reviews")
    prediction: Mapped["PredictionRecord"] = relationship("PredictionRecord", back_populates="reviews")
    reviewer: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<ClinicalReview id={self.id} decision='{self.decision.value}' reviewer_id={self.reviewer_id}>"
