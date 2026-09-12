"""
MedFusion AI — Database Models Package.

Central registry exporting all ORM models for the application and Alembic migrations.
"""

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.user import User, UserRole
from app.models.patient import Patient, BiologicalSex
from app.models.diagnostic_case import DiagnosticCase, CaseModality, CaseStatus
from app.models.image_record import ImageRecord, ImageType
from app.models.clinical_record import ClinicalRecord
from app.models.prediction_record import (
    PredictionRecord,
    ModelType,
    ConfidenceBand,
    PredictionStatus,
)
from app.models.explanation_record import ExplanationRecord, ExplanationType
from app.models.clinical_review import ClinicalReview, ReviewDecision
from app.models.audit_log import AuditLog, AuditAction, AuditResourceType

__all__ = [
    # Base mixins
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    # User & Auth
    "User",
    "UserRole",
    # Patient
    "Patient",
    "BiologicalSex",
    # Diagnostic Case
    "DiagnosticCase",
    "CaseModality",
    "CaseStatus",
    # Modality Records
    "ImageRecord",
    "ImageType",
    "ClinicalRecord",
    # AI Predictions & Explainability
    "PredictionRecord",
    "ModelType",
    "ConfidenceBand",
    "PredictionStatus",
    "ExplanationRecord",
    "ExplanationType",
    # Clinical Review & Compliance
    "ClinicalReview",
    "ReviewDecision",
    "AuditLog",
    "AuditAction",
    "AuditResourceType",
]
