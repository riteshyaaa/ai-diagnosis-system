"""
MedFusion AI — Immutable Audit Log ORM Model.

Maintains an append-only audit trail for all security, compliance,
clinical access, and AI inference events across the system.
"""

from datetime import datetime, timezone
import enum
from typing import Any, Dict, Optional
import uuid
from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class AuditAction(str, enum.Enum):
    """Enumeration of system and user events requiring compliance logging."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_LOCKED = "user_locked"
    USER_REGISTER = "user_register"
    USER_UPDATE = "user_update"
    USER_PASSWORD_CHANGE = "user_password_change"

    PATIENT_CREATE = "patient_create"
    PATIENT_VIEW = "patient_view"
    PATIENT_UPDATE = "patient_update"

    CASE_CREATE = "case_create"
    CASE_VIEW = "case_view"
    CASE_UPDATE = "case_update"
    CASE_DELETE = "case_delete"

    IMAGE_UPLOAD = "image_upload"
    IMAGE_VIEW = "image_view"
    IMAGE_DELETE = "image_delete"
    CLINICAL_RECORD_CREATE = "clinical_record_create"
    CLINICAL_RECORD_UPDATE = "clinical_record_update"
    CLINICAL_RECORD_DELETE = "clinical_record_delete"

    INFERENCE_RUN = "inference_run"
    EXPLANATION_GENERATE = "explanation_generate"
    EXPLANATION_VIEW = "explanation_view"
    EXPLANATION_RECALCULATE = "explanation_recalculate"
    REVIEW_SUBMIT = "review_submit"

    REPORT_EXPORT_PDF = "report_export_pdf"
    DATA_EXPORT = "data_export"
    SYSTEM_CONFIG_CHANGE = "system_config_change"


class AuditResourceType(str, enum.Enum):
    """Resource types targeted by audit events."""
    USER = "user"
    PATIENT = "patient"
    CASE = "case"
    IMAGE = "image"
    CLINICAL_RECORD = "clinical_record"
    PREDICTION = "prediction"
    EXPLANATION = "explanation"
    REVIEW = "review"
    SYSTEM = "system"


class AuditLog(Base, UUIDMixin):
    """Immutable audit trail log record."""

    __tablename__ = "audit_logs"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", create_type=True),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[AuditResourceType] = mapped_column(
        Enum(AuditResourceType, name="audit_resource_type", create_type=True),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Event-specific metadata context",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action='{self.action.value}' user_id={self.user_id} time={self.timestamp}>"
