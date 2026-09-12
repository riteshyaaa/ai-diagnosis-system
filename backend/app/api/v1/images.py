"""
MedFusion AI — Medical Imaging API Endpoints (v1).

Exposes routes for:
- POST   /cases/{case_id}/images      Upload and validate medical radiograph (DICOM / PNG / JPEG)
- GET    /cases/{case_id}/images      List all images attached to a diagnostic case
- GET    /images/{image_id}           Get image metadata
- GET    /images/{image_id}/file      Serve image file artifact (processed, thumbnail, raw)
- DELETE /images/{image_id}           Delete image (DRAFT cases only)
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import FileValidationError
from app.models.image_record import ImageType
from app.models.user import User
from app.schemas.image import (
    ImageListResponse,
    ImageRecordResponse,
    ImageUploadResponse,
)
from app.security.dependencies import (
    get_current_user,
    require_clinical_staff,
    require_clinician,
)
from app.services.image_record_service import ImageRecordService

router = APIRouter(tags=["Medical Imaging"])


@router.post(
    "/cases/{case_id}/images",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Medical Image",
    description="Upload a chest radiograph in DICOM (.dcm), PNG, or JPEG format. Automatically extracts pixels, strips PII, runs quality assurance, and applies CLAHE enhancement.",
)
async def upload_case_image(
    case_id: UUID,
    request: Request,
    file: UploadFile = File(..., description="Radiograph file (DICOM, PNG, or JPEG)"),
    image_type: Optional[ImageType] = Form(None, description="Optional projection override (e.g. chest_xray_pa, chest_xray_ap)"),
    current_user: User = Depends(require_clinical_staff),
    session: AsyncSession = Depends(get_db),
) -> ImageUploadResponse:
    """Upload and process a medical radiograph for a diagnostic case."""
    if not file.filename:
        raise FileValidationError("Upload filename cannot be empty.")

    content = await file.read()
    service = ImageRecordService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.upload_case_image(
        case_id=case_id,
        file_content=content,
        filename=file.filename,
        content_type=file.content_type,
        image_type_override=image_type,
        uploader_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/cases/{case_id}/images",
    response_model=ImageListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Case Images",
    description="Retrieve all radiograph image records linked to a diagnostic case.",
)
async def list_case_images(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ImageListResponse:
    """List images for a case."""
    service = ImageRecordService(session)
    return await service.list_case_images(case_id=case_id)


@router.get(
    "/images/{image_id}",
    response_model=ImageRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Image Metadata",
    description="Retrieve metadata for a specific uploaded radiograph by UUID.",
)
async def get_image(
    image_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ImageRecordResponse:
    """Get image metadata."""
    service = ImageRecordService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.get_image(
        image_id=image_id,
        viewer_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )


@router.get(
    "/images/{image_id}/file",
    status_code=status.HTTP_200_OK,
    summary="Serve Image File Artifact",
    description="Stream image file artifact from secure local storage. Supports 'processed' (standardized PNG), 'thumbnail' (256x256 PNG), and 'raw' (original upload).",
)
async def serve_image_file(
    image_id: UUID,
    variant: str = Query("processed", pattern="^(raw|processed|thumbnail)$", description="Image variant to retrieve"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Serve image file content."""
    service = ImageRecordService(session)
    file_path = await service.get_image_file_path(image_id=image_id, variant=variant)

    media_type = "image/png"
    if file_path.suffix.lower() in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    elif file_path.suffix.lower() == ".dcm":
        media_type = "application/dicom"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )


@router.delete(
    "/images/{image_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Image",
    description="Remove an uploaded radiograph from a case. Only permitted when the parent case is in DRAFT status.",
)
async def delete_image(
    image_id: UUID,
    request: Request,
    current_user: User = Depends(require_clinician),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete image from draft case."""
    service = ImageRecordService(session)
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await service.delete_image(
        image_id=image_id,
        user_id=current_user.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    return {"message": f"Image {image_id} deleted successfully."}
