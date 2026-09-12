"""
MedFusion AI — Human-in-the-Loop Clinical Review Endpoints (v1).

Exposes routes for:
- POST /cases/{case_id}/reviews             Submit a physician review decision (Accept, Modify, Reject)
- GET  /cases/{case_id}/reviews             List all reviews for a diagnostic case
- GET  /predictions/{prediction_id}/reviews List all reviews targeting a specific AI prediction
- GET  /reviews                             List / filter reviews across cases and clinicians
- GET  /reviews/stats                       Aggregate concordance metrics and decision statistics
- GET  /reviews/{review_id}                 Get individual review details
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.clinical_review import ReviewDecision
from app.models.user import User
from app.schemas.clinical_review import (
    ClinicalReviewCreate,
    ClinicalReviewListResponse,
    ClinicalReviewResponse,
    ClinicalReviewStatsResponse,
)
from app.security.dependencies import (
    get_current_user,
    require_clinical_staff,
)
from app.services.clinical_review_service import ClinicalReviewService

router = APIRouter(tags=["Clinical Review & Human-in-the-Loop"])


@router.post(
    "/cases/{case_id}/reviews",
    response_model=ClinicalReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Clinical Review",
    description=(
        "Submit a human-in-the-loop physician review decision (Accept, Modify, Reject) "
        "for an AI prediction on a diagnostic case. Enforces mandatory clinical notes rationale, "
        "updates the case workflow status to REVIEWED, and records an immutable audit trail."
    ),
)
async def submit_case_review(
    case_id: UUID,
    payload: ClinicalReviewCreate,
    request: Request,
    current_user: User = Depends(require_clinical_staff),
    session: AsyncSession = Depends(get_db),
) -> ClinicalReviewResponse:
    """Submit a clinical review decision on a diagnostic case."""
    service = ClinicalReviewService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.submit_review(
        case_id=case_id,
        payload=payload,
        reviewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/cases/{case_id}/reviews",
    response_model=ClinicalReviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Case Reviews",
    description="Retrieve all clinical reviews and physician decisions recorded for a diagnostic case.",
)
async def get_case_reviews(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ClinicalReviewListResponse:
    """List all review records for a specific case."""
    service = ClinicalReviewService(session)
    return await service.get_reviews_by_case(case_id=case_id, user_id=current_user.id)


@router.get(
    "/predictions/{prediction_id}/reviews",
    response_model=ClinicalReviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Prediction Reviews",
    description="Retrieve all clinician feedback and reviews targeting a specific AI prediction.",
)
async def get_prediction_reviews(
    prediction_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ClinicalReviewListResponse:
    """List all review records for a specific prediction."""
    service = ClinicalReviewService(session)
    return await service.get_reviews_by_prediction(
        prediction_id=prediction_id,
        user_id=current_user.id,
    )


@router.get(
    "/reviews/stats",
    response_model=ClinicalReviewStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Clinical Review Statistics",
    description=(
        "Retrieve aggregate human-in-the-loop review statistics, AI concordance rate, "
        "modification and rejection percentages, and top corrected diagnoses."
    ),
)
async def get_review_statistics(
    reviewer_id: Optional[UUID] = Query(None, description="Filter statistics by clinician ID"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ClinicalReviewStatsResponse:
    """Fetch aggregate clinical review statistics and concordance metrics."""
    service = ClinicalReviewService(session)
    return await service.get_review_statistics(
        reviewer_id=reviewer_id,
        user_id=current_user.id,
    )


@router.get(
    "/reviews",
    response_model=ClinicalReviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Reviews",
    description="List and filter all physician reviews across cases and clinicians.",
)
async def list_reviews(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    case_id: Optional[UUID] = Query(None, description="Filter by case ID"),
    reviewer_id: Optional[UUID] = Query(None, description="Filter by reviewing clinician ID"),
    decision: Optional[ReviewDecision] = Query(None, description="Filter by review decision"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ClinicalReviewListResponse:
    """Fetch paginated list of clinical reviews with filtering."""
    service = ClinicalReviewService(session)
    return await service.list_reviews(
        skip=skip,
        limit=limit,
        case_id=case_id,
        reviewer_id=reviewer_id,
        decision=decision,
        user_id=current_user.id,
    )


@router.get(
    "/reviews/{review_id}",
    response_model=ClinicalReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Review Details",
    description="Retrieve full details for an individual clinical review record.",
)
async def get_review_details(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ClinicalReviewResponse:
    """Fetch full details of a specific clinical review."""
    service = ClinicalReviewService(session)
    return await service.get_review_by_id(review_id=review_id, user_id=current_user.id)
