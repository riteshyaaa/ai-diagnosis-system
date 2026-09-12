"""
MedFusion AI — Clinical Record Service.

Orchestrates:
- Tabular clinical measurement ingestion & validation
- Case workflow status gating (editable in DRAFT/SUBMITTED)
- Physiological plausibility validation
- HIPAA/GDPR immutable audit logging (CLINICAL_RECORD_CREATE, VIEW, UPDATE, DELETE)
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError, ValidationError
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.diagnostic_case import CaseStatus
from app.models.clinical_record import ClinicalRecord
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.clinical_record_repository import ClinicalRecordRepository
from app.schemas.clinical_record import (
    ClinicalRecordCreate,
    ClinicalRecordListResponse,
    ClinicalRecordResponse,
    ClinicalRecordUpdate,
    ClinicalRecordWithValidationResponse,
    ClinicalValidationReportSchema,
)
from ml.datasets.heart_disease.validator import ClinicalFeatureValidator


class ClinicalRecordService:
    """Service layer managing clinical tabular records and physiological validation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.record_repo = ClinicalRecordRepository(session)
        self.case_repo = CaseRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def create_record(
        self,
        case_id: UUID,
        data: ClinicalRecordCreate,
        recorder_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ClinicalRecordWithValidationResponse:
        """
        Record structured clinical measurements for a diagnostic case.
        Validates case status, checks physiological plausibility, and records audit trail.
        """
        # 1. Verify Case Existence
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        # 2. Case Workflow Status Constraint
        if case.status not in (CaseStatus.DRAFT, CaseStatus.SUBMITTED):
            raise ValidationError(
                f"Cannot add clinical records to case in '{case.status.value}' status. "
                "Only cases in DRAFT or SUBMITTED state can accept clinical measurements."
            )

        # 3. Clinical Plausibility Validation
        data_dict = data.model_dump()
        val_report = ClinicalFeatureValidator.validate(data_dict)
        if not val_report.is_valid:
            raise ValidationError(
                f"Clinical validation failed: {'; '.join(val_report.errors)}"
            )

        # 4. Construct and Persist Entity
        record_entity = ClinicalRecord(
            case_id=case_id,
            recorded_by_id=recorder_id,
            age=data.age,
            sex=data.sex,
            chest_pain_type=data.chest_pain_type,
            resting_bp=data.resting_bp,
            cholesterol=data.cholesterol,
            fasting_bs=data.fasting_bs,
            resting_ecg=data.resting_ecg,
            max_hr=data.max_hr,
            exercise_angina=data.exercise_angina,
            st_depression=data.st_depression,
            st_slope=data.st_slope,
            num_major_vessels=data.num_major_vessels,
            thalassemia=data.thalassemia,
            bmi=data.bmi,
            smoking_status=data.smoking_status,
            raw_metrics=data.raw_metrics,
        )

        saved = await self.record_repo.create(record_entity)

        # 5. Audit Logging
        await self.audit_repo.log_event(
            action=AuditAction.CLINICAL_RECORD_CREATE,
            resource_type=AuditResourceType.CLINICAL_RECORD,
            resource_id=str(saved.id),
            user_id=recorder_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "case_id": str(case_id),
                "warnings_count": len(val_report.warnings),
                "warnings": val_report.warnings,
            },
        )

        val_schema = ClinicalValidationReportSchema(
            is_valid=val_report.is_valid,
            errors=val_report.errors,
            warnings=val_report.warnings,
            critical_alerts=[w for w in val_report.warnings if "CRITICAL" in w],
        )

        return ClinicalRecordWithValidationResponse(
            record=ClinicalRecordResponse.model_validate(saved),
            validation_report=val_schema,
        )

    async def get_record(
        self,
        record_id: UUID,
        viewer_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ClinicalRecordResponse:
        """Retrieve a specific clinical record by UUID."""
        record = await self.record_repo.get_by_id(record_id)
        if not record:
            raise NotFoundError("ClinicalRecord", record_id)

        return ClinicalRecordResponse.model_validate(record)

    async def list_case_records(self, case_id: UUID) -> ClinicalRecordListResponse:
        """Fetch all clinical measurement sets recorded for a case."""
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        records = await self.record_repo.get_by_case_id(case_id)
        return ClinicalRecordListResponse(
            total=len(records),
            items=[ClinicalRecordResponse.model_validate(r) for r in records],
        )

    async def update_record(
        self,
        record_id: UUID,
        data: ClinicalRecordUpdate,
        updater_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ClinicalRecordResponse:
        """Update clinical record (allowed only in DRAFT cases)."""
        record = await self.record_repo.get_by_id(record_id)
        if not record:
            raise NotFoundError("ClinicalRecord", record_id)

        case = await self.case_repo.get_by_id(record.case_id)
        if case and case.status != CaseStatus.DRAFT:
            raise ValidationError(
                f"Cannot edit clinical record when case is in '{case.status.value}' status. Only DRAFT cases allow edits."
            )

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return ClinicalRecordResponse.model_validate(record)

        # Validate merged data against physiological ranges
        merged_data = ClinicalRecordResponse.model_validate(record).model_dump()
        merged_data.update(update_dict)
        val_report = ClinicalFeatureValidator.validate(merged_data)
        if not val_report.is_valid:
            raise ValidationError(
                f"Clinical validation failed: {'; '.join(val_report.errors)}"
            )

        for key, val in update_dict.items():
            setattr(record, key, val)

        updated = await self.record_repo.update(record)

        await self.audit_repo.log_event(
            action=AuditAction.CLINICAL_RECORD_UPDATE,
            resource_type=AuditResourceType.CLINICAL_RECORD,
            resource_id=str(updated.id),
            user_id=updater_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"updated_fields": list(update_dict.keys())},
        )

        return ClinicalRecordResponse.model_validate(updated)

    async def delete_record(
        self,
        record_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """Delete clinical record (allowed only in DRAFT cases)."""
        record = await self.record_repo.get_by_id(record_id)
        if not record:
            raise NotFoundError("ClinicalRecord", record_id)

        case = await self.case_repo.get_by_id(record.case_id)
        if case and case.status != CaseStatus.DRAFT:
            raise ValidationError(
                f"Cannot delete clinical record when case is in '{case.status.value}' status. Only DRAFT cases allow deletion."
            )

        await self.record_repo.delete(record_id)

        await self.audit_repo.log_event(
            action=AuditAction.CLINICAL_RECORD_DELETE,
            resource_type=AuditResourceType.CLINICAL_RECORD,
            resource_id=str(record_id),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"case_id": str(record.case_id)},
        )

        return True
