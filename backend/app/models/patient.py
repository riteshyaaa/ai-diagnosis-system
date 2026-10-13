"""
MedFusion AI — Patient ORM Model.

Stores patient profiles. MRNs are represented by an unkeyed deterministic hash, which is not de-identification and may be guessable.
"""

import enum
from typing import TYPE_CHECKING, List, Optional
import uuid
from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.diagnostic_case import DiagnosticCase


class BiologicalSex(str, enum.Enum):
    """Biological sex enumeration for clinical stratification."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class Patient(Base, UUIDMixin, TimestampMixin):
    """Patient entity with a non-de-identified MRN digest."""

    __tablename__ = "patients"

    mrn_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="Unkeyed deterministic SHA-256 digest; not de-identification",
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    age: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    sex: Mapped[BiologicalSex] = mapped_column(
        Enum(BiologicalSex, name="biological_sex", create_type=True),
        default=BiologicalSex.UNKNOWN,
        nullable=False,
    )
    blood_group: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    medical_history_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    cases: Mapped[List["DiagnosticCase"]] = relationship(
        "DiagnosticCase",
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="desc(DiagnosticCase.created_at)",
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id} mrn_hash='{self.mrn_hash[:8]}...'>"
