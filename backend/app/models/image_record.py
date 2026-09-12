"""
MedFusion AI — Medical Image Record ORM Model.

Stores metadata, storage paths, dimensions, and cryptographic hashes
for uploaded medical images (chest X-rays).
"""

import enum
from typing import Optional
import uuid
from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ImageType(str, enum.Enum):
    """Radiology image projection types."""
    CHEST_XRAY_PA = "chest_xray_pa"
    CHEST_XRAY_AP = "chest_xray_ap"
    CHEST_XRAY_LATERAL = "chest_xray_lateral"
    OTHER = "other"


class ImageRecord(Base, UUIDMixin, TimestampMixin):
    """Uploaded medical image entity."""

    __tablename__ = "image_records"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Relative path in secure upload storage directory",
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash for data integrity verification",
    )
    image_type: Mapped[ImageType] = mapped_column(
        Enum(ImageType, name="image_type", create_type=True),
        default=ImageType.CHEST_XRAY_PA,
        nullable=False,
    )
    width: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    height: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    channels: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )

    # Relationships
    case: Mapped["DiagnosticCase"] = relationship("DiagnosticCase", back_populates="images")
    uploader: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<ImageRecord id={self.id} filename='{self.original_filename}' type='{self.image_type.value}'>"
