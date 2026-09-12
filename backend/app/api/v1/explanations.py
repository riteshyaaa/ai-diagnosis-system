"""
MedFusion AI — Explainable AI (XAI) & Heatmap Artifact Serving Endpoints (v1).

Exposes routes for:
- GET  /predictions/{prediction_id}/explanation      Full composite explanation (Visual + Tabular + Gating)
- GET  /predictions/{prediction_id}/heatmap          Stream Grad-CAM visual heatmap overlay image file
- GET  /predictions/{prediction_id}/features         SHAP feature attribution waterfall and rankings
- GET  /cases/{case_id}/explanations                 List all historical explanation records for a case
- POST /predictions/{prediction_id}/explain-pathology Recalculate Grad-CAM on-demand for alternative pathology
"""

from pathlib import Path
from typing import Optional
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
        "Retrieve composite clinical explanation for an AI prediction. "
        "Includes Grad-CAM visual attention regions, SHAP tabular feature attributions, "
        "modality late-fusion gating weights, clinical summary text, and mandatory CDSS disclaimers."
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
    summary="Stream Grad-CAM Heatmap Image",
    description="Securely stream the Grad-CAM visual overlay PNG image file for the given prediction.",
)
async def get_prediction_heatmap(
    prediction_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Stream the raw Grad-CAM radiograph overlay image artifact."""
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
    summary="Get SHAP Feature Attributions",
    description=(
        "Retrieve structured SHAP clinical feature waterfall breakdown. "
        "Provides importance ranks, directional impact (risk increasing vs decreasing), "
        "percentage contributions, physiological reference ranges, and contextual interpretations."
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
    summary="Recalculate Pathology Saliency",
    description=(
        "On-demand recalculation of Grad-CAM visual activation heatmaps and localized "
        "attention bounding boxes for an alternative thoracic pathology condition "
        "(e.g. Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass)."
    ),
)
async def recalculate_pathology_saliency(
    prediction_id: UUID,
    request: Request,
    recalc_data: RecalculatePathologySaliencyRequest,
    current_user: User = Depends(require_clinical_staff),
    session: AsyncSession = Depends(get_db),
) -> VisualExplanationResponse:
    """Recompute Grad-CAM visual saliency on-demand for a specific pathology."""
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
