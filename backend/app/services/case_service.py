"""
MedFusion AI — Diagnostic Case Workflow Service.

Encapsulates the clinical diagnostic case lifecycle, workflow state machine,
relational graph aggregation, and audit logging.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import uuid
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DuplicateError, NotFoundError, ValidationError
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.diagnostic_case import CaseModality, CaseStatus, DiagnosticCase
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.case import (
    CaseCreate,
    CaseDetailResponse,
    CaseListResponse,
    CaseResponse,
    CaseUpdate,
)


class CaseService:
    """Service managing diagnostic case workflow, transitions, and aggregation."""

    # Formal workflow state machine transition rules
    VALID_TRANSITIONS: Dict[CaseStatus, Set[CaseStatus]] = {
        CaseStatus.DRAFT: {CaseStatus.SUBMITTED, CaseStatus.ARCHIVED},
        CaseStatus.SUBMITTED: {CaseStatus.PROCESSING, CaseStatus.DRAFT, CaseStatus.ARCHIVED},
        CaseStatus.PROCESSING: {CaseStatus.COMPLETED, CaseStatus.DRAFT, CaseStatus.SUBMITTED, CaseStatus.ARCHIVED},
        CaseStatus.COMPLETED: {CaseStatus.REVIEWED, CaseStatus.SUBMITTED, CaseStatus.ARCHIVED},
        CaseStatus.REVIEWED: {CaseStatus.ARCHIVED, CaseStatus.SUBMITTED},
        CaseStatus.ARCHIVED: {CaseStatus.DRAFT},
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.case_repo = CaseRepository(session)
        self.patient_repo = PatientRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def _generate_unique_case_number(self) -> str:
        """Generate a structured, unique diagnostic case identifier."""
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        for _ in range(10):
            suffix = uuid.uuid4().hex[:6].upper()
            candidate = f"CASE-{today_str}-{suffix}"
            existing = await self.case_repo.get_by_case_number(candidate)
            if not existing:
                return candidate
        # Fallback with timestamp microsecond
        return f"CASE-{today_str}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"

    async def create_case(
        self,
        data: CaseCreate,
        creator_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CaseResponse:
        """
        Create a new diagnostic case in DRAFT status.

        - Verifies that the referenced patient exists
        - Generates or validates unique case number
        - Initializes case in DRAFT status
        - Emits compliance audit log
        """
        patient = await self.patient_repo.get_by_id(data.patient_id)
        if not patient:
            raise NotFoundError("Patient", data.patient_id)

        if data.case_number:
            case_number = data.case_number.strip().upper()
            existing = await self.case_repo.get_by_case_number(case_number)
            if existing:
                raise DuplicateError("DiagnosticCase", "case_number")
        else:
            case_number = await self._generate_unique_case_number()

        new_case = DiagnosticCase(
            case_number=case_number,
            patient_id=data.patient_id,
            created_by_id=creator_id,
            modality=data.modality,
            status=CaseStatus.DRAFT,
            chief_complaint=data.chief_complaint,
            clinical_notes=data.clinical_notes,
        )

        saved = await self.case_repo.create(new_case)

        # Audit log creation
        await self.audit_repo.log_event(
            action=AuditAction.CASE_CREATE,
            resource_type=AuditResourceType.CASE,
            resource_id=str(saved.id),
            user_id=creator_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "case_number": saved.case_number,
                "patient_id": str(saved.patient_id),
                "modality": saved.modality.value,
                "initial_status": saved.status.value,
            },
        )

        return CaseResponse.model_validate(saved)

    async def get_case(
        self,
        case_id: UUID,
        viewer_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        log_view: bool = True,
    ) -> CaseResponse:
        """Retrieve diagnostic case summary by ID."""
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        if log_view:
            await self.audit_repo.log_event(
                action=AuditAction.CASE_VIEW,
                resource_type=AuditResourceType.CASE,
                resource_id=str(case.id),
                user_id=viewer_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return CaseResponse.model_validate(case)

    async def get_case_details(
        self,
        case_id: UUID,
        viewer_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CaseDetailResponse:
        """
        Fetch full diagnostic case details with eager-loaded relational graph:
        Patient, uploaded Images, Clinical Records, Predictions, XAI Explanations, and Reviews.
        """
        case = await self.case_repo.get_full_case_details(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        await self.audit_repo.log_event(
            action=AuditAction.CASE_VIEW,
            resource_type=AuditResourceType.CASE,
            resource_id=str(case.id),
            user_id=viewer_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"view_type": "full_relational_graph"},
        )

        return CaseDetailResponse.model_validate(case)

    async def update_case(
        self,
        case_id: UUID,
        data: CaseUpdate,
        updater_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CaseResponse:
        """Update case details (modality, chief complaint, clinical notes)."""
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        if case.status in (CaseStatus.ARCHIVED, CaseStatus.REVIEWED):
            raise ValidationError(
                f"Cannot modify case in '{case.status.value}' state. Reopen or unarchive the case first."
            )

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return CaseResponse.model_validate(case)

        for key, value in update_dict.items():
            setattr(case, key, value)

        updated = await self.case_repo.update(case)

        await self.audit_repo.log_event(
            action=AuditAction.CASE_UPDATE,
            resource_type=AuditResourceType.CASE,
            resource_id=str(updated.id),
            user_id=updater_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"updated_fields": list(update_dict.keys())},
        )

        return CaseResponse.model_validate(updated)

    async def transition_status(
        self,
        case_id: UUID,
        new_status: CaseStatus,
        reason: Optional[str] = None,
        updater_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CaseResponse:
        """
        Validate and execute a lifecycle state transition on a diagnostic case.

        Enforces workflow constraints:
        - DRAFT -> SUBMITTED, ARCHIVED
        - SUBMITTED -> PROCESSING, DRAFT, ARCHIVED
        - PROCESSING -> COMPLETED, DRAFT, SUBMITTED, ARCHIVED
        - COMPLETED -> REVIEWED, SUBMITTED, ARCHIVED
        - REVIEWED -> ARCHIVED, SUBMITTED
        - ARCHIVED -> DRAFT
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        current_status = case.status
        if current_status == new_status:
            return CaseResponse.model_validate(case)

        valid_targets = self.VALID_TRANSITIONS.get(current_status, set())
        if new_status not in valid_targets:
            target_names = [s.value for s in valid_targets]
            raise ValidationError(
                f"Invalid state transition from '{current_status.value}' to '{new_status.value}'. "
                f"Permitted next states: {target_names}."
            )

        case.status = new_status
        updated = await self.case_repo.update(case)

        await self.audit_repo.log_event(
            action=AuditAction.CASE_UPDATE,
            resource_type=AuditResourceType.CASE,
            resource_id=str(updated.id),
            user_id=updater_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "transition": f"{current_status.value} -> {new_status.value}",
                "old_status": current_status.value,
                "new_status": new_status.value,
                "reason": reason,
            },
        )

        return CaseResponse.model_validate(updated)

    async def list_cases(
        self,
        status: Optional[CaseStatus] = None,
        modality: Optional[CaseModality] = None,
        patient_id: Optional[UUID] = None,
        clinician_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> CaseListResponse:
        """Query and paginate diagnostic cases with multi-criteria filters."""
        stmt = select(DiagnosticCase)
        count_stmt = select(func.count()).select_from(DiagnosticCase)

        if status is not None:
            stmt = stmt.where(DiagnosticCase.status == status)
            count_stmt = count_stmt.where(DiagnosticCase.status == status)
        if modality is not None:
            stmt = stmt.where(DiagnosticCase.modality == modality)
            count_stmt = count_stmt.where(DiagnosticCase.modality == modality)
        if patient_id is not None:
            stmt = stmt.where(DiagnosticCase.patient_id == patient_id)
            count_stmt = count_stmt.where(DiagnosticCase.patient_id == patient_id)
        if clinician_id is not None:
            stmt = stmt.where(DiagnosticCase.created_by_id == clinician_id)
            count_stmt = count_stmt.where(DiagnosticCase.created_by_id == clinician_id)

        stmt = stmt.order_by(DiagnosticCase.created_at.desc()).offset(skip).limit(limit)

        items_res = await self.session.execute(stmt)
        items = list(items_res.scalars().all())

        count_res = await self.session.execute(count_stmt)
        total = count_res.scalar() or 0

        return CaseListResponse(
            total=total,
            items=[CaseResponse.model_validate(c) for c in items],
            skip=skip,
            limit=limit,
        )

    async def delete_case(
        self,
        case_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Delete a diagnostic case (allowed only if case is in DRAFT state).
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        if case.status != CaseStatus.DRAFT:
            raise ValidationError(
                f"Only cases in 'draft' status can be deleted. Case '{case.case_number}' is currently '{case.status.value}'."
            )

        case_number = case.case_number
        await self.case_repo.delete(case_id)

        await self.audit_repo.log_event(
            action=AuditAction.CASE_DELETE,
            resource_type=AuditResourceType.CASE,
            resource_id=str(case_id),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"case_number": case_number},
        )
