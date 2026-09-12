"""
MedFusion AI — Structured Clinical Record API Endpoints (v1).

Exposes routes for:
- POST   /cases/{case_id}/clinical-records     Record patient vitals and lab measurements
- GET    /cases/{case_id}/clinical-records     List all clinical measurement sets for a case
- GET    /clinical-records/{record_id}         Get single clinical record by ID
- PATCH  /clinical-records/{record_id}         Update clinical record measurements (DRAFT only)
- DELETE /clinical-records/{record_id}         Delete clinical record (DRAFT only)
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.clinical_record import (
    ClinicalRecordCreate,
    ClinicalRecordListResponse,
    ClinicalRecordResponse,
    ClinicalRecordUpdate,
    ClinicalRecordWithValidationResponse,
)
from app.security.dependencies import (
    get_current_user,
    require_clinical_staff,
    require_clinician,
)
from app.services.clinical_record_service import ClinicalRecordService

router = APIRouter(tags=["Clinical Records"])


@router.post(
    "/cases/{case_id}/clinical-records",
    response_model=ClinicalRecordWithValidationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Clinical Measurements",
    description="Ingest structured clinical parameters (13 standard UCI Heart Disease features + optional extended metrics) with automated physiological validation and safety alert triggering.",
)
async def create_clinical_record(
    case_id: UUID,
    payload: ClinicalRecordCreate,
    request: Request,
    current_user: User = Depends(require_clinical_staff),
    session: AsyncSession = Depends(get_db),
) -> ClinicalRecordWithValidationResponse:
    """Record patient clinical measurements for a case."""
    service = ClinicalRecordService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.create_record(
        case_id=case_id,
        data=payload,
        recorder_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/cases/{case_id}/clinical-records",
    response_model=ClinicalRecordListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Case Clinical Records",
    description="Retrieve all clinical measurement sets linked to a diagnostic case.",
)
async def list_case_clinical_records(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ClinicalRecordListResponse:
    """List clinical measurement records for a diagnostic case."""
    service = ClinicalRecordService(session)
    return await service.list_case_records(case_id=case_id)


@router.get(
    "/clinical-records/{record_id}",
    response_model=ClinicalRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Clinical Record",
    description="Retrieve a single clinical measurement record by UUID.",
)
async def get_clinical_record(
    record_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ClinicalRecordResponse:
    """Get single clinical record by ID."""
    service = ClinicalRecordService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.get_record(
        record_id=record_id,
        viewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.patch(
    "/clinical-records/{record_id}",
    response_model=ClinicalRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Clinical Record",
    description="Update measurements on an existing clinical record. Allowed only while the parent case is in DRAFT status.",
)
async def update_clinical_record(
    record_id: UUID,
    payload: ClinicalRecordUpdate,
    request: Request,
    current_user: User = Depends(require_clinician),
    session: AsyncSession = Depends(get_db),
) -> ClinicalRecordResponse:
    """Update clinical record measurements in DRAFT case."""
    service = ClinicalRecordService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.update_record(
        record_id=record_id,
        data=payload,
        updater_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.delete(
    "/clinical-records/{record_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Clinical Record",
    description="Remove a clinical record from a case. Allowed only while the parent case is in DRAFT status.",
)
async def delete_clinical_record(
    record_id: UUID,
    request: Request,
    current_user: User = Depends(require_clinician),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete clinical record from draft case."""
    service = ClinicalRecordService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    await service.delete_record(
        record_id=record_id,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    return {"message": f"Clinical record {record_id} deleted successfully."}
