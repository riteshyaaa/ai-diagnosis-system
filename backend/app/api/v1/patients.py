"""
MedFusion AI — Patient Management API Endpoints (v1).

Exposes routes for:
- POST   /patients          Register new de-identified patient
- GET    /patients          List and filter patients with pagination
- GET    /patients/{id}     Retrieve patient demographic profile
- GET    /patients/mrn/{mrn} Lookup patient by MRN
- PATCH  /patients/{id}     Update patient demographic attributes
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.patient import BiologicalSex
from app.models.user import User
from app.schemas.patient import (
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientUpdate,
)
from app.security.dependencies import (
    get_current_user,
    require_clinical_staff,
    require_clinician,
)
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Patient",
    description="Register a new de-identified patient record. The raw MRN is SHA-256 hashed immediately; raw MRN is never stored.",
)
async def create_patient(
    patient_data: PatientCreate,
    request: Request,
    current_user: User = Depends(require_clinician),
    session: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Register a new de-identified patient."""
    service = PatientService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.create_patient(
        data=patient_data,
        creator_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "",
    response_model=PatientListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Patients",
    description="Retrieve paginated list of de-identified patient records with optional demographic filtering.",
)
async def list_patients(
    sex: Optional[BiologicalSex] = Query(None, description="Filter by biological sex"),
    min_age: Optional[int] = Query(None, ge=0, le=125, description="Filter by minimum age"),
    max_age: Optional[int] = Query(None, ge=0, le=125, description="Filter by maximum age"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PatientListResponse:
    """Query and filter de-identified patients."""
    service = PatientService(session)
    return await service.list_patients(
        sex=sex,
        min_age=min_age,
        max_age=max_age,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Patient Profile",
    description="Fetch a de-identified patient profile by UUID.",
)
async def get_patient(
    patient_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Fetch patient by UUID."""
    service = PatientService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.get_patient(
        patient_id=patient_id,
        viewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/search/mrn",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Patient by MRN",
    description="Search for an existing patient record by raw MRN (hashed in memory to perform the lookup).",
)
async def search_patient_by_mrn(
    request: Request,
    mrn: str = Query(..., min_length=1, description="Raw Medical Record Number to search"),
    current_user: User = Depends(require_clinical_staff),
    session: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Lookup patient by raw MRN."""
    service = PatientService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.get_patient_by_mrn(
        raw_mrn=mrn,
        viewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.patch(
    "/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Patient",
    description="Update demographic or medical history attributes of a patient.",
)
async def update_patient(
    patient_id: UUID,
    update_data: PatientUpdate,
    request: Request,
    current_user: User = Depends(require_clinician),
    session: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """Update patient demographic details."""
    service = PatientService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.update_patient(
        patient_id=patient_id,
        update_data=update_data,
        updater_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
