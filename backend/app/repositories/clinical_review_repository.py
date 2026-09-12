"""
MedFusion AI — Clinical Review Repository.

Encapsulates database operations for human clinician supervision reviews:
- Reviews by case and prediction
- Clinician review history
- Decision statistics and concordance metrics (Accept, Modify, Reject)
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_review import ClinicalReview, ReviewDecision
from app.models.diagnostic_case import DiagnosticCase
from app.models.prediction_record import PredictionRecord
from app.repositories.base import BaseRepository


class ClinicalReviewRepository(BaseRepository[ClinicalReview]):
    """Repository managing human-in-the-loop clinical review records."""

    def __init__(self, session: AsyncSession):
        super().__init__(ClinicalReview, session)

    async def get_by_id_with_details(self, review_id: UUID) -> Optional[ClinicalReview]:
        """Fetch a specific review by ID with reviewer, case, and prediction preloaded."""
        stmt = (
            select(ClinicalReview)
            .where(ClinicalReview.id == review_id)
            .options(
                selectinload(ClinicalReview.reviewer),
                selectinload(ClinicalReview.case),
                selectinload(ClinicalReview.prediction),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_case_id(self, case_id: UUID) -> List[ClinicalReview]:
        """Fetch all reviews submitted for a case with reviewer and prediction."""
        stmt = (
            select(ClinicalReview)
            .where(ClinicalReview.case_id == case_id)
            .options(
                selectinload(ClinicalReview.reviewer),
                selectinload(ClinicalReview.prediction),
            )
            .order_by(ClinicalReview.reviewed_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_prediction_id(self, prediction_id: UUID) -> List[ClinicalReview]:
        """Fetch all reviews targeting a specific AI prediction."""
        stmt = (
            select(ClinicalReview)
            .where(ClinicalReview.prediction_id == prediction_id)
            .options(
                selectinload(ClinicalReview.reviewer),
                selectinload(ClinicalReview.case),
            )
            .order_by(ClinicalReview.reviewed_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_reviewer(
        self,
        reviewer_id: UUID,
        decision: Optional[ReviewDecision] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ClinicalReview]:
        """Fetch all reviews authored by a specific clinician with optional decision filtering."""
        items, _ = await self.list_reviews(
            skip=skip,
            limit=limit,
            reviewer_id=reviewer_id,
            decision=decision,
        )
        return items

    async def list_reviews(
        self,
        skip: int = 0,
        limit: int = 50,
        case_id: Optional[UUID] = None,
        reviewer_id: Optional[UUID] = None,
        decision: Optional[ReviewDecision] = None,
    ) -> Tuple[List[ClinicalReview], int]:
        """Fetch paginated reviews with optional filtering by case, reviewer, or decision."""
        base_query = select(ClinicalReview)
        count_query = select(func.count(ClinicalReview.id))

        if case_id is not None:
            base_query = base_query.where(ClinicalReview.case_id == case_id)
            count_query = count_query.where(ClinicalReview.case_id == case_id)

        if reviewer_id is not None:
            base_query = base_query.where(ClinicalReview.reviewer_id == reviewer_id)
            count_query = count_query.where(ClinicalReview.reviewer_id == reviewer_id)

        if decision is not None:
            base_query = base_query.where(ClinicalReview.decision == decision)
            count_query = count_query.where(ClinicalReview.decision == decision)

        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        stmt = (
            base_query
            .options(
                selectinload(ClinicalReview.reviewer),
                selectinload(ClinicalReview.case),
                selectinload(ClinicalReview.prediction),
            )
            .order_by(ClinicalReview.reviewed_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def get_statistics(self, reviewer_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Calculate aggregate decision counts and concordance metrics."""
        base_filter = []
        if reviewer_id is not None:
            base_filter.append(ClinicalReview.reviewer_id == reviewer_id)

        # Count total reviews
        total_stmt = select(func.count(ClinicalReview.id))
        if base_filter:
            total_stmt = total_stmt.where(*base_filter)
        total_result = await self.session.execute(total_stmt)
        total_reviews = total_result.scalar_one() or 0

        if total_reviews == 0:
            return {
                "total_reviews": 0,
                "accepted_count": 0,
                "modified_count": 0,
                "rejected_count": 0,
                "concordance_rate": 0.0,
                "modification_rate": 0.0,
                "rejection_rate": 0.0,
                "top_modified_diagnoses": [],
            }

        # Breakdown by decision
        decision_stmt = (
            select(ClinicalReview.decision, func.count(ClinicalReview.id))
        )
        if base_filter:
            decision_stmt = decision_stmt.where(*base_filter)
        decision_stmt = decision_stmt.group_by(ClinicalReview.decision)
        decision_result = await self.session.execute(decision_stmt)
        decision_counts = {dec: cnt for dec, cnt in decision_result.all()}

        accepted = decision_counts.get(ReviewDecision.ACCEPT, 0)
        modified = decision_counts.get(ReviewDecision.MODIFY, 0)
        rejected = decision_counts.get(ReviewDecision.REJECT, 0)

        concordance_rate = round((accepted / total_reviews) * 100, 2)
        modification_rate = round((modified / total_reviews) * 100, 2)
        rejection_rate = round((rejected / total_reviews) * 100, 2)

        # Top modified diagnoses
        mod_stmt = (
            select(ClinicalReview.modified_diagnosis, func.count(ClinicalReview.id).label("cnt"))
            .where(
                ClinicalReview.decision == ReviewDecision.MODIFY,
                ClinicalReview.modified_diagnosis.isnot(None),
            )
        )
        if base_filter:
            mod_stmt = mod_stmt.where(*base_filter)
        mod_stmt = (
            mod_stmt
            .group_by(ClinicalReview.modified_diagnosis)
            .order_by(func.count(ClinicalReview.id).desc())
            .limit(10)
        )
        mod_result = await self.session.execute(mod_stmt)
        top_modified = [
            {"diagnosis": diag, "count": cnt}
            for diag, cnt in mod_result.all() if diag
        ]

        return {
            "total_reviews": total_reviews,
            "accepted_count": accepted,
            "modified_count": modified,
            "rejected_count": rejected,
            "concordance_rate": concordance_rate,
            "modification_rate": modification_rate,
            "rejection_rate": rejection_rate,
            "top_modified_diagnoses": top_modified,
        }
