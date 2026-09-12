"""
MedFusion AI — Diagnostic Case Repository.

Encapsulates database operations for clinical diagnostic cases:
- Case number lookups and uniqueness checks
- Multi-modal case filtering (by status, modality, patient, clinician)
- Eager retrieval of deep relational graphs (patient, images, tabular records, predictions, XAI, reviews)
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnostic_case import DiagnosticCase, CaseModality, CaseStatus
from app.models.prediction_record import PredictionRecord
from app.repositories.base import BaseRepository


class CaseRepository(BaseRepository[DiagnosticCase]):
    """Repository for managing diagnostic cases across all modalities."""

    def __init__(self, session: AsyncSession):
        super().__init__(DiagnosticCase, session)

    async def get_by_case_number(self, case_number: str) -> Optional[DiagnosticCase]:
        """Fetch a case by unique case number identifier."""
        stmt = select(DiagnosticCase).where(DiagnosticCase.case_number == case_number)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_full_case_details(self, case_id: UUID) -> Optional[DiagnosticCase]:
        """
        Fetch a complete diagnostic case with all associated multimodal inputs,
        AI predictions, XAI explanations, and physician review decisions.
        """
        stmt = (
            select(DiagnosticCase)
            .where(DiagnosticCase.id == case_id)
            .options(
                selectinload(DiagnosticCase.patient),
                selectinload(DiagnosticCase.creator),
                selectinload(DiagnosticCase.images),
                selectinload(DiagnosticCase.clinical_records),
                selectinload(DiagnosticCase.predictions).selectinload(PredictionRecord.explanation),
                selectinload(DiagnosticCase.predictions).selectinload(PredictionRecord.reviews),
                selectinload(DiagnosticCase.reviews),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_status(
        self,
        status: CaseStatus,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DiagnosticCase]:
        """Fetch cases by workflow status (e.g. DRAFT, PROCESSING, REVIEWED)."""
        stmt = (
            select(DiagnosticCase)
            .where(DiagnosticCase.status == status)
            .order_by(DiagnosticCase.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_patient(
        self,
        patient_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DiagnosticCase]:
        """Fetch all diagnostic cases for a specific patient."""
        stmt = (
            select(DiagnosticCase)
            .where(DiagnosticCase.patient_id == patient_id)
            .order_by(DiagnosticCase.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_clinician(
        self,
        clinician_id: UUID,
        status: Optional[CaseStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DiagnosticCase]:
        """Fetch cases created by a specific clinician with optional status filter."""
        stmt = select(DiagnosticCase).where(DiagnosticCase.created_by_id == clinician_id)
        if status is not None:
            stmt = stmt.where(DiagnosticCase.status == status)
        stmt = stmt.order_by(DiagnosticCase.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
