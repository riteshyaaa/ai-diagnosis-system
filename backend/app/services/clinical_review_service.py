"""
MedFusion AI — Human-in-the-Loop Clinical Review Service.

Orchestrates clinician supervision workflows, review submissions,
decision tracking (Accept, Modify, Reject), case lifecycle progression,
audit compliance logging, and aggregate concordance analytics.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError, ValidationError
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.clinical_review import ClinicalReview, ReviewDecision
from app.models.diagnostic_case import CaseStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.clinical_review_repository import ClinicalReviewRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.clinical_review import (
    CLINICAL_DISCLAIMER_TEXT,
    ClinicalReviewCreate,
    ClinicalReviewListResponse,
    ClinicalReviewResponse,
    ClinicalReviewStatsResponse,
    ReviewerSummary,
)

logger = logging.getLogger("medfusion.clinical_review")


class ClinicalReviewService:
    """Service orchestrating clinician supervision and human-in-the-loop workflows."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.review_repo = ClinicalReviewRepository(session)
        self.case_repo = CaseRepository(session)
        self.prediction_repo = PredictionRepository(session)
        self.user_repo = UserRepository(session)
        self.audit_repo = AuditLogRepository(session)

    def _format_review_response(
        self,
        review: ClinicalReview,
        case_number: Optional[str] = None,
        ai_predicted_diagnosis: Optional[str] = None,
    ) -> ClinicalReviewResponse:
        """Format an ORM ClinicalReview into a full ClinicalReviewResponse."""
        reviewer_summary = None
        if review.reviewer:
            reviewer_summary = ReviewerSummary(
                id=review.reviewer.id,
                email=review.reviewer.email,
                full_name=review.reviewer.full_name,
                role=review.reviewer.role.value if hasattr(review.reviewer.role, "value") else str(review.reviewer.role),
                department=getattr(review.reviewer, "department", None),
            )

        c_number = case_number
        if not c_number and review.case:
            c_number = review.case.case_number

        ai_diag = ai_predicted_diagnosis
        if not ai_diag and review.prediction:
            ai_diag = review.prediction.primary_condition

        concordance = (review.decision == ReviewDecision.ACCEPT)

        return ClinicalReviewResponse(
            id=review.id,
            case_id=review.case_id,
            prediction_id=review.prediction_id,
            reviewer_id=review.reviewer_id,
            decision=review.decision,
            modified_diagnosis=review.modified_diagnosis,
            clinical_notes=review.clinical_notes,
            reviewed_at=review.reviewed_at,
            created_at=review.created_at,
            reviewer=reviewer_summary,
            case_number=c_number,
            ai_predicted_diagnosis=ai_diag,
            concordance=concordance,
            clinical_disclaimer=CLINICAL_DISCLAIMER_TEXT,
        )

    async def submit_review(
        self,
        case_id: UUID,
        payload: ClinicalReviewCreate,
        reviewer_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ClinicalReviewResponse:
        """
        Submit a human-in-the-loop review for an AI prediction on a diagnostic case.
        Transitions the case to REVIEWED status and logs an immutable audit event.
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        # Determine target prediction
        prediction_id = payload.prediction_id
        if prediction_id is None:
            # Select the most recent prediction for this case
            predictions = await self.prediction_repo.get_by_case_id(case_id)
            if not predictions:
                raise ValidationError("Cannot review a case with no AI predictions. Run prediction first.")
            target_pred = predictions[0]
            prediction_id = target_pred.id
        else:
            target_pred = await self.prediction_repo.get_by_id(prediction_id)
            if not target_pred or target_pred.case_id != case_id:
                raise ValidationError("The specified prediction does not belong to this case.")

        # Validate MODIFY decision constraints
        if payload.decision == ReviewDecision.MODIFY:
            if not payload.modified_diagnosis or not payload.modified_diagnosis.strip():
                raise ValidationError("A modified diagnosis is mandatory when selecting decision 'modify'.")
        elif payload.decision == ReviewDecision.ACCEPT:
            # If accepted, modified_diagnosis is cleared
            payload.modified_diagnosis = None

        # Create review entity
        review = ClinicalReview(
            case_id=case_id,
            prediction_id=prediction_id,
            reviewer_id=reviewer_id,
            decision=payload.decision,
            modified_diagnosis=payload.modified_diagnosis.strip() if payload.modified_diagnosis else None,
            clinical_notes=payload.clinical_notes.strip(),
            reviewed_at=datetime.now(timezone.utc),
        )
        await self.review_repo.create(review)

        # Transition Case workflow state to REVIEWED
        case.status = CaseStatus.REVIEWED
        await self.session.commit()

        # Audit Trail Logging
        await self.audit_repo.log_event(
            action=AuditAction.REVIEW_SUBMIT,
            resource_type=AuditResourceType.REVIEW,
            resource_id=str(review.id),
            user_id=reviewer_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "case_id": str(case_id),
                "case_number": case.case_number,
                "prediction_id": str(prediction_id),
                "decision": payload.decision.value,
                "modified_diagnosis": review.modified_diagnosis,
                "ai_predicted_diagnosis": target_pred.primary_condition,
                "concordance": payload.decision == ReviewDecision.ACCEPT,
            },
        )

        # Fetch loaded review with relations for full response
        loaded_review = await self.review_repo.get_by_id_with_details(review.id)
        if not loaded_review:
            loaded_review = review

        logger.info(
            "Clinician %s submitted review for case %s (Decision: %s)",
            reviewer_id,
            case.case_number,
            payload.decision.value,
        )

        return self._format_review_response(
            loaded_review,
            case_number=case.case_number,
            ai_predicted_diagnosis=target_pred.primary_condition,
        )

    async def get_review_by_id(
        self,
        review_id: UUID,
        user_id: UUID,
    ) -> ClinicalReviewResponse:
        """Retrieve a specific clinical review by ID."""
        review = await self.review_repo.get_by_id_with_details(review_id)
        if not review:
            raise NotFoundError("ClinicalReview", review_id)
        return self._format_review_response(review)

    async def get_reviews_by_case(
        self,
        case_id: UUID,
        user_id: UUID,
    ) -> ClinicalReviewListResponse:
        """Retrieve all clinical reviews submitted for a diagnostic case."""
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        reviews = await self.review_repo.get_by_case_id(case_id)
        items = [
            self._format_review_response(r, case_number=case.case_number)
            for r in reviews
        ]
        return ClinicalReviewListResponse(total=len(items), items=items)

    async def get_reviews_by_prediction(
        self,
        prediction_id: UUID,
        user_id: UUID,
    ) -> ClinicalReviewListResponse:
        """Retrieve all reviews associated with a specific AI prediction."""
        pred = await self.prediction_repo.get_by_id(prediction_id)
        if not pred:
            raise NotFoundError("PredictionRecord", prediction_id)

        reviews = await self.review_repo.get_by_prediction_id(prediction_id)
        items = [
            self._format_review_response(r, ai_predicted_diagnosis=pred.primary_condition)
            for r in reviews
        ]
        return ClinicalReviewListResponse(total=len(items), items=items)

    async def list_reviews(
        self,
        skip: int = 0,
        limit: int = 50,
        case_id: Optional[UUID] = None,
        reviewer_id: Optional[UUID] = None,
        decision: Optional[ReviewDecision] = None,
        user_id: Optional[UUID] = None,
    ) -> ClinicalReviewListResponse:
        """Fetch paginated reviews with optional filtering."""
        reviews, total = await self.review_repo.list_reviews(
            skip=skip,
            limit=limit,
            case_id=case_id,
            reviewer_id=reviewer_id,
            decision=decision,
        )
        items = [self._format_review_response(r) for r in reviews]
        return ClinicalReviewListResponse(total=total, items=items)

    async def get_review_statistics(
        self,
        reviewer_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> ClinicalReviewStatsResponse:
        """Compute aggregate review statistics, concordance rates, and recent feedback."""
        stats = await self.review_repo.get_statistics(reviewer_id=reviewer_id)

        # Retrieve up to 5 most recent reviews
        recent_reviews_orm, _ = await self.review_repo.list_reviews(
            skip=0,
            limit=5,
            reviewer_id=reviewer_id,
        )
        recent_formatted = [self._format_review_response(r) for r in recent_reviews_orm]

        return ClinicalReviewStatsResponse(
            total_reviews=stats["total_reviews"],
            accepted_count=stats["accepted_count"],
            modified_count=stats["modified_count"],
            rejected_count=stats["rejected_count"],
            concordance_rate=stats["concordance_rate"],
            modification_rate=stats["modification_rate"],
            rejection_rate=stats["rejection_rate"],
            top_modified_diagnoses=stats["top_modified_diagnoses"],
            recent_reviews=recent_formatted,
            clinical_disclaimer=CLINICAL_DISCLAIMER_TEXT,
        )
