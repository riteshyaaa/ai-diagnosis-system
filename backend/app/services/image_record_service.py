"""
MedFusion AI — Medical Image Record Service.

Manages image lifecycle, case association, file serving, and audit logging.
"""

from pathlib import Path
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFoundError, ValidationError
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.diagnostic_case import CaseStatus
from app.models.image_record import ImageRecord, ImageType
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.image_repository import ImageRepository
from app.schemas.image import (
    ImageListResponse,
    ImageQualityReportSchema,
    ImageRecordResponse,
    ImageUploadResponse,
)
from app.services.image_processing_service import ImageProcessingService


class ImageRecordService:
    """Service layer for medical radiograph storage, metadata, and case linkages."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.image_repo = ImageRepository(session)
        self.case_repo = CaseRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.processing_service = ImageProcessingService()
        self.settings = get_settings()

    async def upload_case_image(
        self,
        case_id: UUID,
        file_content: bytes,
        filename: str,
        content_type: Optional[str] = None,
        image_type_override: Optional[ImageType] = None,
        uploader_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ImageUploadResponse:
        """
        Ingest, validate, preprocess, and link a medical radiograph to an active case.
        """
        # 1. Verify case exists and allows image uploads (DRAFT or SUBMITTED)
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        if case.status not in (CaseStatus.DRAFT, CaseStatus.SUBMITTED):
            raise ValidationError(
                f"Cannot upload images to case in '{case.status.value}' status. Only DRAFT and SUBMITTED cases accept new data."
            )

        # 2. Run image processing pipeline
        processed = await self.processing_service.process_image_upload(
            content=file_content,
            original_filename=filename,
            content_type=content_type,
            image_type_override=image_type_override,
        )

        # 3. Create ImageRecord database entity
        image_record = ImageRecord(
            case_id=case_id,
            uploaded_by_id=uploader_id,
            file_path=processed.processed_storage_path,
            original_filename=processed.original_filename,
            file_size_bytes=processed.file_size_bytes,
            mime_type=processed.mime_type,
            file_hash=processed.file_hash,
            image_type=processed.image_type,
            width=processed.width,
            height=processed.height,
            channels=processed.channels,
        )

        saved = await self.image_repo.create(image_record)

        # 4. Audit Trail Logging
        await self.audit_repo.log_event(
            action=AuditAction.IMAGE_UPLOAD,
            resource_type=AuditResourceType.IMAGE,
            resource_id=str(saved.id),
            user_id=uploader_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "case_id": str(case_id),
                "original_filename": filename,
                "file_hash": processed.file_hash,
                "quality_score": processed.quality_report.quality_score,
                "dimensions": f"{processed.width}x{processed.height}",
            },
        )

        # 5. Build response
        quality_schema = ImageQualityReportSchema(
            is_valid=processed.quality_report.is_valid,
            quality_score=processed.quality_report.quality_score,
            width=processed.quality_report.width,
            height=processed.quality_report.height,
            aspect_ratio=processed.quality_report.aspect_ratio,
            mean_intensity=processed.quality_report.mean_intensity,
            contrast_std=processed.quality_report.contrast_std,
            sharpness_score=processed.quality_report.sharpness_score,
            issues=processed.quality_report.issues,
            warnings=processed.quality_report.warnings,
        )

        return ImageUploadResponse(
            image=ImageRecordResponse.model_validate(saved),
            quality_report=quality_schema,
            technical_metadata=processed.technical_metadata,
        )

    async def get_image(
        self,
        image_id: UUID,
        viewer_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ImageRecordResponse:
        """Fetch image metadata by ID and record audit view event."""
        image = await self.image_repo.get_by_id(image_id)
        if not image:
            raise NotFoundError("ImageRecord", image_id)

        await self.audit_repo.log_event(
            action=AuditAction.IMAGE_VIEW,
            resource_type=AuditResourceType.IMAGE,
            resource_id=str(image.id),
            user_id=viewer_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"case_id": str(image.case_id)},
        )

        return ImageRecordResponse.model_validate(image)

    async def list_case_images(self, case_id: UUID) -> ImageListResponse:
        """Fetch all images linked to a diagnostic case."""
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        images = await self.image_repo.get_by_case_id(case_id)
        return ImageListResponse(
            total=len(images),
            items=[ImageRecordResponse.model_validate(img) for img in images],
        )

    async def get_image_file_path(
        self,
        image_id: UUID,
        variant: str = "processed",  # "raw", "processed", "thumbnail"
    ) -> Path:
        """Get absolute path to image file on local storage."""
        image = await self.image_repo.get_by_id(image_id)
        if not image:
            raise NotFoundError("ImageRecord", image_id)

        base_upload = Path(self.settings.upload_dir).resolve()

        if variant == "thumbnail":
            path = base_upload / "images" / "thumbnails" / f"{image.file_hash}_thumb.png"
        elif variant == "raw":
            # Find matching file in raw directory
            raw_dir = base_upload / "images" / "raw"
            matches = list(raw_dir.glob(f"{image.file_hash}.*"))
            path = matches[0] if matches else (raw_dir / f"{image.file_hash}.png")
        else:
            path = base_upload / "images" / "processed" / f"{image.file_hash}_processed.png"

        if not path.exists():
            raise NotFoundError(f"Image file artifact ({variant})", image_id)

        return path

    async def delete_image(
        self,
        image_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """Delete an image record from a case. Only allowed when case is in DRAFT status."""
        image = await self.image_repo.get_by_id(image_id)
        if not image:
            raise NotFoundError("ImageRecord", image_id)

        case = await self.case_repo.get_by_id(image.case_id)
        if case and case.status != CaseStatus.DRAFT:
            raise ValidationError(
                f"Cannot delete images from case in '{case.status.value}' status. Only DRAFT cases can be modified."
            )

        await self.image_repo.delete(image_id)

        await self.audit_repo.log_event(
            action=AuditAction.IMAGE_DELETE,
            resource_type=AuditResourceType.IMAGE,
            resource_id=str(image_id),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"case_id": str(image.case_id), "file_hash": image.file_hash},
        )
        return True
