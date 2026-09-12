"""
MedFusion AI — AI Prediction & Inference API Endpoints (v1).

Exposes routes for:
- POST /cases/{case_id}/predict          Execute AI inference on an existing diagnostic case
- GET  /cases/{case_id}/predictions      List all prediction runs for a case
- GET  /cases/{case_id}/predictions/latest Get the latest prediction run for a case
- GET  /predictions/{prediction_id}      Get specific prediction record with explanation
- GET  /predictions                      List and filter all prediction records
- POST /predictions/direct               Execute direct real-time standalone inference
- POST /predictions/direct-upload        Execute direct inference with multipart image upload
"""

import json
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import ValidationError
from app.models.prediction_record import PredictionStatus
from app.models.user import User
from app.schemas.prediction import (
    CasePredictRequest,
    DirectPredictRequest,
    PredictionListResponse,
    PredictionResponse,
)
from app.security.dependencies import (
    get_current_user,
    require_clinical_staff,
)
from app.services.ai_inference_service import AIInferenceService

router = APIRouter(tags=["AI Prediction & Inference"])


@router.post(
    "/cases/{case_id}/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute Case AI Prediction",
    description=(
        "Trigger multimodal or unimodal AI diagnostic inference for a diagnostic case. "
        "Fuses chest radiograph visual representations with structured clinical telemetry, "
        "calibrates probabilities, computes uncertainty metrics, generates Grad-CAM/SHAP XAI artifacts, "
        "advances case workflow state to COMPLETED, and enforces mandatory CDSS regulatory disclaimers."
    ),
)
async def predict_case(
    case_id: UUID,
    request: Request,
    predict_data: Optional[CasePredictRequest] = None,
    current_user: User = Depends(require_clinical_staff),
    session: AsyncSession = Depends(get_db),
) -> PredictionResponse:
    """Execute AI inference on a diagnostic case."""
    service = AIInferenceService(session)
    payload = predict_data or CasePredictRequest()
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.predict_case(
        case_id=case_id,
        request_data=payload,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/cases/{case_id}/predictions",
    response_model=PredictionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Case Predictions",
    description="Retrieve all historical AI prediction runs executed for a diagnostic case.",
)
async def get_case_predictions(
    case_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PredictionListResponse:
    """Fetch all prediction records for a case."""
    service = AIInferenceService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.get_case_predictions(
        case_id=case_id,
        viewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/cases/{case_id}/predictions/latest",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Latest Case Prediction",
    description="Retrieve the most recent AI prediction record and associated explainability artifacts for a case.",
)
async def get_latest_case_prediction(
    case_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PredictionResponse:
    """Fetch the latest prediction record for a case."""
    service = AIInferenceService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.get_latest_case_prediction(
        case_id=case_id,
        viewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/predictions/{prediction_id}",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Prediction by ID",
    description="Retrieve a specific AI prediction record including calibrated probabilities, uncertainty scores, and XAI artifacts.",
)
async def get_prediction_by_id(
    prediction_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PredictionResponse:
    """Fetch a prediction record by its UUID."""
    service = AIInferenceService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.get_prediction(
        prediction_id=prediction_id,
        viewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/predictions",
    response_model=PredictionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List All Predictions",
    description="Query and paginate prediction records across cases with optional safety status filtering.",
)
async def list_predictions(
    prediction_status: Optional[PredictionStatus] = Query(None, alias="status", description="Filter by prediction safety status"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PredictionListResponse:
    """List prediction records across the platform."""
    service = AIInferenceService(session)
    return await service.list_predictions(
        status=prediction_status,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/predictions/direct",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Direct Real-Time Inference (JSON)",
    description="Execute standalone real-time inference using JSON payload without persisting to a case.",
)
async def direct_prediction_json(
    direct_req: DirectPredictRequest,
    request: Request,
    current_user: User = Depends(require_clinical_staff),
    session: AsyncSession = Depends(get_db),
) -> PredictionResponse:
    """Run direct inference on clinical data."""
    service = AIInferenceService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.predict_direct(
        request_data=direct_req,
        image_bytes=None,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.post(
    "/predictions/direct-upload",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Direct Real-Time Inference (Multipart Image Upload)",
    description="Execute standalone real-time inference with a radiograph file upload and optional tabular clinical JSON.",
)
async def direct_prediction_upload(
    request: Request,
    file: Optional[UploadFile] = File(None, description="Radiograph file (DICOM, PNG, JPEG)"),
    tabular_features_json: Optional[str] = Form(None, description="JSON string of structured clinical telemetry"),
    patient_mrn: Optional[str] = Form(None, description="Patient MRN for privacy-hashed tracking"),
    generate_explainability: bool = Form(True, description="Whether to compute Grad-CAM and SHAP artifacts"),
    model_version: Optional[str] = Form(None, description="Target model version"),
    current_user: User = Depends(require_clinical_staff),
    session: AsyncSession = Depends(get_db),
) -> PredictionResponse:
    """Run direct inference with multipart radiograph file upload."""
    image_bytes = None
    if file:
        image_bytes = await file.read()

    tabular_dict = None
    if tabular_features_json:
        try:
            tabular_dict = json.loads(tabular_features_json)
        except Exception as e:
            raise ValidationError(f"Invalid tabular_features_json format: {e}")

    req_data = DirectPredictRequest(
        patient_mrn=patient_mrn,
        tabular_features=tabular_dict,
        generate_explainability=generate_explainability,
        model_version=model_version,
    )

    service = AIInferenceService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.predict_direct(
        request_data=req_data,
        image_bytes=image_bytes,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
