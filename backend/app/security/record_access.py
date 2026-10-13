"""Object-level access checks for records without a team-sharing model."""

from uuid import UUID

from app.exceptions import NotFoundError
from app.models.diagnostic_case import DiagnosticCase
from app.models.patient import Patient


def require_patient_owner(
    patient: Patient | None, patient_id: UUID, user_id: UUID | None
) -> Patient:
    """Return a patient only to its creator; hide missing and foreign records alike."""
    if patient is None or user_id is None or patient.created_by_id != user_id:
        raise NotFoundError("Patient", patient_id)
    return patient


def require_case_owner(
    case: DiagnosticCase | None, case_id: UUID, user_id: UUID | None
) -> DiagnosticCase:
    """Return a case only to its creator; hide missing and foreign records alike."""
    if case is None or user_id is None or case.created_by_id != user_id:
        raise NotFoundError("DiagnosticCase", case_id)
    return case
