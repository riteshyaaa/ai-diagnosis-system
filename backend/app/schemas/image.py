"""
MedFusion AI — Medical Image Pydantic Schemas.

Defines schemas for:
- Medical image metadata representation
- Quantitative quality validation reporting
- Image list pagination and query responses
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.image_record import ImageType


class ImageQualityReportSchema(BaseModel):
    """Quantitative quality assessment and validation details."""
    is_valid: bool
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Composite diagnostic quality score (0-1)")
    width: int
    height: int
    aspect_ratio: float
    mean_intensity: float
    contrast_std: float
    sharpness_score: float
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ImageRecordResponse(BaseModel):
    """Uploaded medical image metadata response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    uploaded_by_id: UUID
    original_filename: str
    file_size_bytes: int
    mime_type: str
    file_hash: str
    image_type: ImageType
    width: Optional[int] = None
    height: Optional[int] = None
    channels: int
    created_at: datetime
    updated_at: datetime


class ImageUploadResponse(BaseModel):
    """Response returned upon successful medical image upload and validation."""
    image: ImageRecordResponse
    quality_report: ImageQualityReportSchema
    technical_metadata: Dict[str, Any] = Field(default_factory=dict)


class ImageListResponse(BaseModel):
    """Paginated list of medical image records."""
    total: int
    items: List[ImageRecordResponse]
