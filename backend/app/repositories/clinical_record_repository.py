"""
MedFusion AI — Clinical Record Repository.

Encapsulates database operations for structured clinical/tabular measurements:
- Case clinical data retrieval
- Chronological measurement tracking
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_record import ClinicalRecord
from app.repositories.base import BaseRepository


class ClinicalRecordRepository(BaseRepository[ClinicalRecord]):
    """Repository managing structured clinical records."""

    def __init__(self, session: AsyncSession):
        super().__init__(ClinicalRecord, session)

    async def get_by_case_id(self, case_id: UUID) -> List[ClinicalRecord]:
        """Fetch all clinical measurement sets for a given case."""
        stmt = (
            select(ClinicalRecord)
            .where(ClinicalRecord.case_id == case_id)
            .order_by(ClinicalRecord.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_case_id(self, case_id: UUID) -> Optional[ClinicalRecord]:
        """Fetch the most recent clinical measurement set for a given case."""
        stmt = (
            select(ClinicalRecord)
            .where(ClinicalRecord.case_id == case_id)
            .order_by(ClinicalRecord.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
