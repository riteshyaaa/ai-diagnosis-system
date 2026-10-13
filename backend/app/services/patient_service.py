"""Patient management with owner-scoped records and audit-event writes.

MRN values are stored as unkeyed deterministic SHA-256 digests, which are not
anonymization and may be vulnerable to guessing.
"""

import hashlib
import re
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.exceptions import DuplicateError, NotFoundError, ValidationError
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.patient import Patient, BiologicalSex
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.patient_repository import PatientRepository
from app.security.record_access import require_patient_owner
from app.schemas.patient import PatientCreate, PatientListResponse, PatientResponse, PatientUpdate


class PatientService:
    """Service managing patient records and audit events."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.patient_repo = PatientRepository(session)
        self.audit_repo = AuditLogRepository(session)

    @staticmethod
    def hash_mrn(raw_mrn: str) -> str:
        """
        Compute an unkeyed deterministic SHA-256 digest of an MRN.
        This prevents direct storage of the input but does not de-identify it.
        """
        normalized_mrn = raw_mrn.strip().upper()
        return hashlib.sha256(normalized_mrn.encode("utf-8")).hexdigest()

    async def create_patient(
        self,
        data: PatientCreate,
        creator_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PatientResponse:
        """
        Register a new de-identified patient record.

        - Hashes raw MRN or validates provided MRN hash
        - Enforces uniqueness on mrn_hash
        - Persists patient record
        - Records an audit event
        """
        if data.mrn:
            mrn_hash = self.hash_mrn(data.mrn)
        elif data.mrn_hash:
            if not re.match(r"^[a-fA-F0-9]{64}$", data.mrn_hash):
                raise ValidationError("MRN hash must be a valid 64-character hexadecimal SHA-256 string.")
            mrn_hash = data.mrn_hash.lower()
        else:
            raise ValidationError("Either 'mrn' or 'mrn_hash' must be provided.")

        existing = await self.patient_repo.get_by_mrn_hash(mrn_hash)
        if existing:
            raise DuplicateError("Patient", "MRN")

        patient = Patient(
            mrn_hash=mrn_hash,
            created_by_id=creator_id,
            age=data.age,
            sex=data.sex,
            blood_group=data.blood_group,
            medical_history_summary=data.medical_history_summary,
        )

        saved = await self.patient_repo.create(patient)

        # Audit log event
        await self.audit_repo.log_event(
            action=AuditAction.PATIENT_CREATE,
            resource_type=AuditResourceType.PATIENT,
            resource_id=str(saved.id),
            user_id=creator_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "mrn_hash_prefix": mrn_hash[:8] + "...",
                "age": saved.age,
                "sex": saved.sex.value if saved.sex else None,
            },
        )

        return PatientResponse.model_validate(saved)

    async def get_patient(
        self,
        patient_id: UUID,
        viewer_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        log_view: bool = True,
    ) -> PatientResponse:
        """Fetch patient record by UUID with optional audit logging."""
        patient = require_patient_owner(
            await self.patient_repo.get_by_id(patient_id), patient_id, viewer_id
        )

        if log_view:
            await self.audit_repo.log_event(
                action=AuditAction.PATIENT_VIEW,
                resource_type=AuditResourceType.PATIENT,
                resource_id=str(patient.id),
                user_id=viewer_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return PatientResponse.model_validate(patient)

    async def get_patient_by_mrn(
        self,
        raw_mrn: str,
        viewer_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PatientResponse:
        """Lookup patient by raw MRN by hashing and querying the hash."""
        mrn_hash = self.hash_mrn(raw_mrn)
        patient = await self.patient_repo.get_by_mrn_hash(mrn_hash)
        if not patient:
            raise NotFoundError("Patient with provided MRN")
        patient = require_patient_owner(patient, patient.id, viewer_id)

        await self.audit_repo.log_event(
            action=AuditAction.PATIENT_VIEW,
            resource_type=AuditResourceType.PATIENT,
            resource_id=str(patient.id),
            user_id=viewer_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"lookup_method": "mrn_search"},
        )

        return PatientResponse.model_validate(patient)

    async def list_patients(
        self,
        viewer_id: UUID,
        sex: Optional[BiologicalSex] = None,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> PatientListResponse:
        """List and filter de-identified patients with total count pagination."""
        items = await self.patient_repo.filter_patients(
            creator_id=viewer_id,
            sex=sex,
            min_age=min_age,
            max_age=max_age,
            skip=skip,
            limit=limit,
        )

        # Count total matching records
        count_stmt = select(func.count()).select_from(Patient).where(
            Patient.created_by_id == viewer_id
        )
        if sex is not None:
            count_stmt = count_stmt.where(Patient.sex == sex)
        if min_age is not None:
            count_stmt = count_stmt.where(Patient.age >= min_age)
        if max_age is not None:
            count_stmt = count_stmt.where(Patient.age <= max_age)

        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        return PatientListResponse(
            total=total,
            items=[PatientResponse.model_validate(p) for p in items],
            skip=skip,
            limit=limit,
        )

    async def update_patient(
        self,
        patient_id: UUID,
        update_data: PatientUpdate,
        updater_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PatientResponse:
        """Update patient demographic and medical history attributes."""
        patient = require_patient_owner(
            await self.patient_repo.get_by_id(patient_id), patient_id, updater_id
        )

        update_dict = update_data.model_dump(exclude_unset=True)
        if not update_dict:
            return PatientResponse.model_validate(patient)

        for key, value in update_dict.items():
            setattr(patient, key, value)

        updated = await self.patient_repo.update(patient)

        await self.audit_repo.log_event(
            action=AuditAction.PATIENT_UPDATE,
            resource_type=AuditResourceType.PATIENT,
            resource_id=str(updated.id),
            user_id=updater_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"updated_fields": list(update_dict.keys())},
        )

        return PatientResponse.model_validate(updated)
