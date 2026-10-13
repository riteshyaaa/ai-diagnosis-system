"""
MedFusion AI — Prediction Record Repository.

Encapsulates database operations for AI inference outputs:
- Case prediction retrieval
- Eager loading of associated XAI explanation artifacts
- Safety status and confidence band filtering
"""

from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction_record import (
    PredictionRecord,
    PredictionStatus,
)
from app.models.diagnostic_case import DiagnosticCase
from app.repositories.base import BaseRepository


class PredictionRepository(BaseRepository[PredictionRecord]):
    """Repository managing AI prediction records."""

    def __init__(self, session: AsyncSession):
        super().__init__(PredictionRecord, session)

    async def get_by_case_id(self, case_id: UUID) -> List[PredictionRecord]:
        """Fetch all AI predictions generated for a diagnostic case."""
        stmt = (
            select(PredictionRecord)
            .where(PredictionRecord.case_id == case_id)
            .options(selectinload(PredictionRecord.explanation))
            .order_by(PredictionRecord.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_explanation(self, prediction_id: UUID) -> Optional[PredictionRecord]:
        """Fetch a specific prediction with its XAI explanation record eagerly loaded."""
        stmt = (
            select(PredictionRecord)
            .where(PredictionRecord.id == prediction_id)
            .options(selectinload(PredictionRecord.explanation))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_latest_by_case_id(self, case_id: UUID) -> Optional[PredictionRecord]:
        """Fetch the most recent prediction generated for a case."""
        stmt = (
            select(PredictionRecord)
            .where(PredictionRecord.case_id == case_id)
            .options(selectinload(PredictionRecord.explanation))
            .order_by(PredictionRecord.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_status(
        self,
        status: PredictionStatus,
        skip: int = 0,
        limit: int = 50,
    ) -> List[PredictionRecord]:
        """Fetch predictions filtered by clinical status (e.g., ABSTAINED, UNCERTAIN)."""
        stmt = (
            select(PredictionRecord)
            .where(PredictionRecord.status == status)
            .order_by(PredictionRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_case_owner(
        self,
        owner_id: UUID,
        status: Optional[PredictionStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[PredictionRecord], int]:
        """List predictions only for cases owned by the requesting user."""
        query = (
            select(PredictionRecord)
            .join(DiagnosticCase, PredictionRecord.case_id == DiagnosticCase.id)
            .where(DiagnosticCase.created_by_id == owner_id)
        )
        count_query = (
            select(func.count(PredictionRecord.id))
            .join(DiagnosticCase, PredictionRecord.case_id == DiagnosticCase.id)
            .where(DiagnosticCase.created_by_id == owner_id)
        )
        if status is not None:
            query = query.where(PredictionRecord.status == status)
            count_query = count_query.where(PredictionRecord.status == status)

        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()
        query = (
            query.options(selectinload(PredictionRecord.explanation))
            .order_by(PredictionRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all()), total
