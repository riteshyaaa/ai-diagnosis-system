"""
MedFusion AI — Patient ORM Model.

Stores anonymized patient profiles with privacy-preserving Medical Record Number (MRN) hashes.
No raw personally identifiable information (PII) is persisted.
"""

import enum
from typing import List, Optional
from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class BiologicalSex(str, enum.Enum):
    """Biological sex enumeration for clinical stratification."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class Patient(Base, UUIDMixin, TimestampMixin):
    """Anonymized patient entity."""

    __tablename__ = "patients"

    mrn_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="SHA-256 hash of the medical record number for de-identification",
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
