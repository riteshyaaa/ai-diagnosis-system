"""
MedFusion AI — Image Record Repository.

Encapsulates database operations on diagnostic medical imaging metadata:
- Case image lookup
- File integrity hash deduplication and validation
- Modality-based retrieval
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image_record import ImageRecord, ImageType
from app.repositories.base import BaseRepository


class ImageRepository(BaseRepository[ImageRecord]):
    """Repository for managing uploaded medical image records."""

    def __init__(self, session: AsyncSession):
        super().__init__(ImageRecord, session)

    async def get_by_case_id(self, case_id: UUID) -> List[ImageRecord]:
        """Fetch all image records associated with a diagnostic case."""
        stmt = (
            select(ImageRecord)
            .where(ImageRecord.case_id == case_id)
            .order_by(ImageRecord.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_hash(self, file_hash: str) -> Optional[ImageRecord]:
        """Lookup an image record by its SHA-256 integrity hash."""
        stmt = select(ImageRecord).where(ImageRecord.file_hash == file_hash)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_image_type(
        self,
        image_type: ImageType,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ImageRecord]:
        """Fetch images filtered by projection type (PA, AP, Lateral)."""
        stmt = (
            select(ImageRecord)
            .where(ImageRecord.image_type == image_type)
            .order_by(ImageRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
