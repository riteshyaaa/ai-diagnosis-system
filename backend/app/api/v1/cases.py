"""
MedFusion AI — Diagnostic Case API Endpoints (v1).

Exposes routes for:
- POST   /cases                  Create new diagnostic case (DRAFT)
- GET    /cases                  List and filter cases by status/modality/patient/clinician
- GET    /cases/{id}             Get case summary
- GET    /cases/{id}/details     Get full case details (Patient, Images, Tabular, Predictions, XAI, Reviews)
- PATCH  /cases/{id}             Update case metadata
- POST   /cases/{id}/status      Execute lifecycle state transition
- DELETE /cases/{id}             Delete case (DRAFT state only)
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.diagnostic_case import CaseModality, CaseStatus
from app.models.user import User
from app.schemas.case import (
    CaseCreate,
    CaseDetailResponse,
    CaseListResponse,
    CaseResponse,
    CaseStatusUpdate,
    CaseUpdate,
)
from app.security.dependencies import (
    get_current_user,
    require_clinician,
)
from app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["Diagnostic Cases"])


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Diagnostic Case",
    description="Create a new diagnostic case linked to a patient in DRAFT status.",
)
async def create_case(
    case_data: CaseCreate,
    request: Request,
    current_user: User = Depends(require_clinician),
    session: AsyncSession = Depends(get_db),
) -> CaseResponse:
    """Create a new diagnostic case in DRAFT status."""
    service = CaseService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.create_case(
        data=case_data,
        creator_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "",
    response_model=CaseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Diagnostic Cases",
    description="Query and paginate diagnostic cases with multi-criteria filtering by status, modality, patient, or clinician.",
)
async def list_cases(
    case_status: Optional[CaseStatus] = Query(None, alias="status", description="Filter by workflow status"),
    modality: Optional[CaseModality] = Query(None, description="Filter by case modality"),
    patient_id: Optional[UUID] = Query(None, description="Filter by patient ID"),
    clinician_id: Optional[UUID] = Query(None, description="Filter by creating clinician ID"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseListResponse:
    """List and filter diagnostic cases."""
    service = CaseService(session)
    return await service.list_cases(
        status=case_status,
        modality=modality,
        patient_id=patient_id,
        clinician_id=clinician_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Case Summary",
    description="Retrieve top-level summary of a diagnostic case by UUID.",
)
async def get_case(
    case_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseResponse:
    """Fetch diagnostic case summary."""
    service = CaseService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.get_case(
        case_id=case_id,
        viewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/{case_id}/details",
    response_model=CaseDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Complete Case Relational Graph",
    description="Retrieve comprehensive case graph including Patient profile, Images, Clinical Records, Predictions, XAI Explanations, and Clinician Reviews.",
)
async def get_case_details(
    case_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseDetailResponse:
    """Fetch full relational details for a case."""
    service = CaseService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.get_case_details(
        case_id=case_id,
        viewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.patch(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Case Metadata",
    description="Update modality, chief complaint, or clinical notes of an active case.",
)
async def update_case(
    case_id: UUID,
    update_data: CaseUpdate,
    request: Request,
    current_user: User = Depends(require_clinician),
    session: AsyncSession = Depends(get_db),
) -> CaseResponse:
    """Update case metadata."""
    service = CaseService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.update_case(
        case_id=case_id,
        data=update_data,
        updater_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.post(
    "/{case_id}/status",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Transition Case Status",
    description="Advance or change the case lifecycle status according to formal state machine constraints.",
)
async def transition_case_status(
    case_id: UUID,
    status_data: CaseStatusUpdate,
    request: Request,
    current_user: User = Depends(require_clinician),
    session: AsyncSession = Depends(get_db),
) -> CaseResponse:
    """Execute workflow state transition on a diagnostic case."""
    service = CaseService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.transition_status(
        case_id=case_id,
        new_status=status_data.status,
        reason=status_data.reason,
        updater_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.delete(
    "/{case_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Case",
    description="Permanently delete a diagnostic case. Allowed only when case is in DRAFT status.",
)
async def delete_case(
    case_id: UUID,
    request: Request,
    current_user: User = Depends(require_clinician),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete draft diagnostic case."""
    service = CaseService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await service.delete_case(
        case_id=case_id,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    return {"message": f"Diagnostic case {case_id} deleted successfully."}
