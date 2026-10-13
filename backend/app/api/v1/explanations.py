"""Routes for reading stored attribution artifacts and requesting recalculation.

Artifacts may be absent when no compatible model produced them; returned attribution
is not clinically validated or evidence of disease localization.
"""

from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.explainability import (
    ExplanationListResponse,
    ExplanationResponse,
    FeatureAttributionsResponse,
    RecalculatePathologySaliencyRequest,
    VisualExplanationResponse,
)
from app.security.dependencies import (
    get_current_user,
    require_clinical_staff,
)
from app.services.explainability_service import ExplainabilityService

router = APIRouter(tags=["Explainable AI (XAI) & Artifacts"])


@router.get(
    "/predictions/{prediction_id}/explanation",
    response_model=ExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Prediction Explanation",
    description=(
        "Retrieve explanation artifacts that were actually stored for this prediction. "
        "Visual attribution, tabular attribution, or modality details may be absent when "
        "the required model artifact was unavailable. Stored attribution is not clinically validated."
    ),
)
async def get_prediction_explanation(
    prediction_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ExplanationResponse:
    """Fetch complete explainability record for a specific prediction."""
    service = ExplainabilityService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.get_explanation_by_prediction_id(
        prediction_id=prediction_id,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/predictions/{prediction_id}/heatmap",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
    summary="Download Stored Heatmap Artifact",
    description=(
        "Download a heatmap PNG only when one was generated and stored for this prediction. "
        "A heatmap is model attribution and does not establish disease localization."
    ),
)
async def get_prediction_heatmap(
    prediction_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Stream a previously stored heatmap artifact."""
    service = ExplainabilityService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    file_path: Path = await service.get_heatmap_file_path(
        prediction_id=prediction_id,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )

    return FileResponse(
        path=str(file_path),
        media_type="image/png",
        filename=f"gradcam_{prediction_id}.png",
    )


@router.get(
    "/predictions/{prediction_id}/features",
    response_model=FeatureAttributionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Stored Feature Attributions",
    description=(
        "Retrieve tabular attribution values stored for this prediction, when available. "
        "The endpoint does not infer clinical reference ranges or causal effects; attribution "
        "requires a compatible model and a provenance-backed background dataset."
    ),
)
async def get_feature_attributions(
    prediction_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FeatureAttributionsResponse:
    """Fetch ranked SHAP feature attribution waterfall."""
    service = ExplainabilityService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.get_tabular_feature_attributions(
        prediction_id=prediction_id,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/cases/{case_id}/explanations",
    response_model=ExplanationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Case Explanations",
    description="Retrieve all historical AI explainability records generated for a diagnostic case.",
)
async def get_case_explanations(
    case_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ExplanationListResponse:
    """Fetch all explanation records associated with a diagnostic case."""
    service = ExplainabilityService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.get_explanations_by_case_id(
        case_id=case_id,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.post(
    "/predictions/{prediction_id}/explain-pathology",
    response_model=VisualExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Request Alternate Visual Attribution",
    description=(
        "Request model-derived visual attribution for an alternate supported target. This "
        "operation is unavailable when the required compatible model artifact is missing. "
        "Attribution does not establish anatomical disease localization."
    ),
)
async def recalculate_pathology_saliency(
    prediction_id: UUID,
    request: Request,
    recalc_data: RecalculatePathologySaliencyRequest,
    current_user: User = Depends(require_clinical_staff),
    session: AsyncSession = Depends(get_db),
) -> VisualExplanationResponse:
    """Request visual attribution for a target when a compatible model is available."""
    service = ExplainabilityService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.recalculate_pathology_saliency(
        prediction_id=prediction_id,
        request_data=recalc_data,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
