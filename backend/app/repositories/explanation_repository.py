"""
MedFusion AI — Explanation Record Repository.

Encapsulates database operations for explainability artifacts:
- Grad-CAM heatmap paths
- SHAP feature attributions
- Human-readable clinical summaries
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.explanation_record import ExplanationRecord
from app.models.prediction_record import PredictionRecord
from app.repositories.base import BaseRepository


class ExplanationRepository(BaseRepository[ExplanationRecord]):
    """Repository managing XAI explanation artifacts."""

    def __init__(self, session: AsyncSession):
        super().__init__(ExplanationRecord, session)

    async def get_by_prediction_id(self, prediction_id: UUID) -> Optional[ExplanationRecord]:
        """Fetch the unique explanation artifact for a given prediction."""
        stmt = select(ExplanationRecord).where(ExplanationRecord.prediction_id == prediction_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_case_id(self, case_id: UUID) -> List[ExplanationRecord]:
        """Fetch all explanation artifacts associated with a diagnostic case."""
        stmt = (
            select(ExplanationRecord)
            .join(PredictionRecord, ExplanationRecord.prediction_id == PredictionRecord.id)
            .where(PredictionRecord.case_id == case_id)
            .order_by(ExplanationRecord.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
