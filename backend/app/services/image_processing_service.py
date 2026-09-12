"""
MedFusion AI — Medical Image Processing & Ingestion Service.

Orchestrates:
- Raw byte stream validation and SHA-256 cryptographic hashing
- Format dispatch (DICOM .dcm vs Standard PNG/JPEG)
- De-identification and metadata scrubbing
- Automated diagnostic quality validation
- CLAHE contrast enhancement and model tensor preparation (1, 3, 224, 224)
- Secure local artifact storage (raw, processed, thumbnail)
"""

from dataclasses import dataclass, field
import hashlib
import io
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image
import torch

from app.config import get_settings
from app.exceptions import FileValidationError
from app.models.image_record import ImageType
from ml.datasets.chest_xray.dicom_parser import DicomParser, DicomParseResult
from ml.datasets.chest_xray.quality_validator import (
    ImageQualityReport,
    ImageQualityValidator,
)
from ml.datasets.chest_xray.transforms import MedicalImageTransforms


@dataclass
class ProcessedImageResult:
    """Output payload from the image ingestion and preprocessing pipeline."""
    file_hash: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    image_type: ImageType
    width: int
    height: int
    channels: int
    raw_storage_path: str
    processed_storage_path: str
    thumbnail_storage_path: str
    quality_report: ImageQualityReport
    technical_metadata: Dict[str, Any] = field(default_factory=dict)
    tensor: Optional[torch.Tensor] = None


class ImageProcessingService:
    """Service for processing, validating, enhancing, and storing medical chest radiographs."""

    def __init__(self, upload_base_dir: Optional[str] = None):
        self.settings = get_settings()
        self.base_dir = Path(upload_base_dir or self.settings.upload_dir)

        # Storage directory paths
        self.raw_dir = self.base_dir / "images" / "raw"
        self.processed_dir = self.base_dir / "images" / "processed"
        self.thumb_dir = self.base_dir / "images" / "thumbnails"

        # Ensure storage directories exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.thumb_dir.mkdir(parents=True, exist_ok=True)

        self.transforms = MedicalImageTransforms()

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        """Compute SHA-256 cryptographic hash of byte stream."""
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def is_dicom_bytes(cls, content: bytes) -> bool:
        """Check if byte stream represents a DICOM file."""
        if len(content) > 132 and content[128:132] == b"DICM":
            return True
        # Some DICOM files lack preamble; check magic element tags
        if content.startswith(b"\x08\x00") or content.startswith(b"\x02\x00"):
            return True
        return False

    async def process_image_upload(
        self,
        content: bytes,
        original_filename: str,
        content_type: Optional[str] = None,
        image_type_override: Optional[ImageType] = None,
    ) -> ProcessedImageResult:
        """
        Ingest, validate, de-identify, enhance, and persist an uploaded medical radiograph.
        Supports both DICOM (.dcm) and standard formats (.png, .jpg, .jpeg).
        """
        # 1. Size validation
        file_size = len(content)
        if file_size == 0:
            raise FileValidationError("Uploaded file is empty.")
        if file_size > self.settings.max_upload_size_bytes:
            raise FileValidationError(
                f"File size ({file_size / (1024*1024):.1f} MB) exceeds maximum allowed ({self.settings.max_upload_size_mb} MB)."
            )

        # 2. Compute SHA-256 integrity hash
        file_hash = self.compute_sha256(content)

        # 3. Format detection and pixel extraction
        is_dicom = (
            self.is_dicom_bytes(content)
            or original_filename.lower().endswith((".dcm", ".dicom"))
            or content_type == "application/dicom"
        )

        technical_meta: Dict[str, Any] = {}

        if is_dicom:
            dicom_res = DicomParser.parse_from_bytes(content)
            rgb_array = dicom_res.pixel_array
            detected_type = dicom_res.image_type
            technical_meta = dicom_res.technical_metadata
            mime_type = "application/dicom"
            raw_ext = ".dcm"
        else:
            try:
                pil_img = Image.open(io.BytesIO(content))
                pil_img = pil_img.convert("RGB")
                rgb_array = np.array(pil_img)
            except Exception as e:
                raise FileValidationError(f"Invalid image format or corrupted image file: {str(e)}")

            detected_type = ImageType.CHEST_XRAY_PA
            mime_type = content_type or "image/png"
            raw_ext = Path(original_filename).suffix.lower() or ".png"

        image_type = image_type_override or detected_type
        height, width = rgb_array.shape[:2]

        # 4. Quality Assurance & Validation
        quality_report = ImageQualityValidator.validate_image(rgb_array)
        if not quality_report.is_valid:
            error_details = "; ".join(quality_report.issues)
            raise FileValidationError(f"Medical image quality validation failed: {error_details}")

        # 5. Preprocessing & Contrast Enhancement (CLAHE)
        tensor, enhanced_rgb = self.transforms.preprocess_for_inference(rgb_array, use_clahe=True)

        # 6. Save artifacts to secure storage
        # (a) Raw file
        raw_filename = f"{file_hash}{raw_ext}"
        raw_path = self.raw_dir / raw_filename
        if not raw_path.exists():
            with open(raw_path, "wb") as f:
                f.write(content)

        # (b) Processed standardized PNG (enhanced)
        processed_filename = f"{file_hash}_processed.png"
        processed_path = self.processed_dir / processed_filename
        if not processed_path.exists():
            processed_pil = Image.fromarray(enhanced_rgb)
            processed_pil.save(processed_path, format="PNG")

        # (c) Thumbnail PNG (256x256)
        thumb_filename = f"{file_hash}_thumb.png"
        thumb_path = self.thumb_dir / thumb_filename
        if not thumb_path.exists():
            thumb_pil = Image.fromarray(enhanced_rgb)
            thumb_pil.thumbnail((256, 256), Image.Resampling.LANCZOS)
            thumb_pil.save(thumb_path, format="PNG")

        return ProcessedImageResult(
            file_hash=file_hash,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size_bytes=file_size,
            image_type=image_type,
            width=width,
            height=height,
            channels=3,
            raw_storage_path=str(raw_path.relative_to(self.base_dir.parent)),
            processed_storage_path=str(processed_path.relative_to(self.base_dir.parent)),
            thumbnail_storage_path=str(thumb_path.relative_to(self.base_dir.parent)),
            quality_report=quality_report,
            technical_metadata=technical_meta,
            tensor=tensor,
        )

    def load_processed_tensor_from_disk(self, processed_path_str: str) -> torch.Tensor:
        """Load an existing processed PNG from disk and return normalized inference tensor."""
        full_path = self.base_dir.parent / processed_path_str
        if not full_path.exists():
            raise FileValidationError(f"Processed image artifact not found: {processed_path_str}")
        pil_img = Image.open(full_path).convert("RGB")
        tensor, _ = self.transforms.preprocess_for_inference(pil_img, use_clahe=False)
        return tensor
