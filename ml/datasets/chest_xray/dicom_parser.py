"""
MedFusion AI — DICOM Ingestion & Privacy De-Identification Parser.

Handles:
- In-memory DICOM parsing from raw byte streams or file paths
- Radiograph pixel normalization (PhotometricInterpretation MONOCHROME1 inversion, VOI LUT / Windowing)
- Strict de-identification: strips all HIPAA / GDPR PII fields (PatientName, ID, BirthDate, Institution, etc.)
- Technical metadata extraction (pixel spacing, view position, dimensions, dynamic range)
"""

from dataclasses import dataclass, field
import io
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import pydicom
from pydicom.dataset import Dataset

from app.exceptions import FileValidationError
from app.models.image_record import ImageType
from ml.datasets.chest_xray.transforms import MedicalImageTransforms


@dataclass
class DicomParseResult:
    """Standardized parsed DICOM payload."""
    pixel_array: np.ndarray  # uint8 RGB array (H, W, 3)
    width: int
    height: int
    channels: int
    image_type: ImageType
    is_dicom: bool
    technical_metadata: Dict[str, Any] = field(default_factory=dict)


class DicomParser:
    """Parses, de-identifies, and normalizes clinical DICOM radiographs."""

    # Explicit whitelist of safe technical DICOM tags (No PII)
    SAFE_METADATA_TAGS = {
        "Modality",
        "BodyPartExamined",
        "ViewPosition",
        "PatientOrientation",
        "PhotometricInterpretation",
        "Rows",
        "Columns",
        "PixelSpacing",
        "ImagerPixelSpacing",
        "BitsAllocated",
        "BitsStored",
        "HighBit",
        "PixelRepresentation",
        "WindowCenter",
        "WindowWidth",
        "RescaleSlope",
        "RescaleIntercept",
        "LossyImageCompression",
        "KVP",
        "DistanceSourceToDetector",
    }

    @classmethod
    def parse_from_bytes(cls, raw_bytes: bytes) -> DicomParseResult:
        """Parse DICOM from raw byte stream, extract pixels and de-identify metadata."""
        try:
            ds: Dataset = pydicom.dcmread(io.BytesIO(raw_bytes), force=True)
            return cls._process_dataset(ds)
        except Exception as e:
            raise FileValidationError(f"Invalid or unreadable DICOM file: {str(e)}")

    @classmethod
    def parse_from_file(cls, file_path: str) -> DicomParseResult:
        """Parse DICOM from local filesystem path."""
        try:
            ds: Dataset = pydicom.dcmread(file_path, force=True)
            return cls._process_dataset(ds)
        except Exception as e:
            raise FileValidationError(f"Invalid or unreadable DICOM file: {str(e)}")

    @classmethod
    def _process_dataset(cls, ds: Dataset) -> DicomParseResult:
        """Core dataset processing and de-identification."""
        # 1. Extract raw pixel array
        try:
            raw_pixels = ds.pixel_array.astype(np.float32)
        except Exception as e:
            raise FileValidationError(f"DICOM file contains no readable pixel data: {str(e)}")

        # 2. Extract technical parameters
        photometric = getattr(ds, "PhotometricInterpretation", "MONOCHROME2").strip().upper()
        rescale_slope = float(getattr(ds, "RescaleSlope", 1.0))
        rescale_intercept = float(getattr(ds, "RescaleIntercept", 0.0))

        # Handle window center & width (could be MultiValue or float)
        window_center = cls._extract_float_tag(ds, "WindowCenter")
        window_width = cls._extract_float_tag(ds, "WindowWidth")

        # 3. Handle MONOCHROME1 (invert to standard MONOCHROME2 where bone is bright)
        if photometric == "MONOCHROME1":
            raw_pixels = np.max(raw_pixels) - raw_pixels

        # 4. Apply VOI LUT / Windowing
        windowed_8bit = MedicalImageTransforms.apply_windowing(
            pixel_array=raw_pixels,
            window_center=window_center,
            window_width=window_width,
            rescale_slope=rescale_slope,
            rescale_intercept=rescale_intercept,
        )

        # 5. Convert to standard 3-channel RGB uint8
        rgb_image = MedicalImageTransforms.ensure_3channel_rgb(windowed_8bit)

        # 6. Map ViewPosition to ImageType
        view_pos = str(getattr(ds, "ViewPosition", "")).strip().upper()
        image_type = cls._map_view_position(view_pos)

        # 7. Extract sanitized technical metadata (PII stripped)
        sanitized_meta = {}
        for tag in cls.SAFE_METADATA_TAGS:
            if hasattr(ds, tag):
                val = getattr(ds, tag)
                sanitized_meta[tag] = cls._serialize_dicom_value(val)

        height, width = rgb_image.shape[:2]

        return DicomParseResult(
            pixel_array=rgb_image,
            width=width,
            height=height,
            channels=3,
            image_type=image_type,
            is_dicom=True,
            technical_metadata=sanitized_meta,
        )

    @staticmethod
    def _extract_float_tag(ds: Dataset, tag: str) -> Optional[float]:
        """Safely extract float tag that may be single value, sequence, or string."""
        if not hasattr(ds, tag):
            return None
        val = getattr(ds, tag)
        try:
            if isinstance(val, (list, tuple, pydicom.multival.MultiValue)):
                return float(val[0])
            return float(val)
        except (ValueError, TypeError, IndexError):
            return None

    @staticmethod
    def _map_view_position(view_pos: str) -> ImageType:
        """Map DICOM ViewPosition tag to ImageType enum."""
        if view_pos in ("PA", "POSTEROANTERIOR"):
            return ImageType.CHEST_XRAY_PA
        elif view_pos in ("AP", "ANTEROPOSTERIOR", "AP ERECT", "AP SUPINE"):
            return ImageType.CHEST_XRAY_AP
        elif view_pos in ("LATERAL", "LAT", "LL", "RL", "L", "R"):
            return ImageType.CHEST_XRAY_LATERAL
        return ImageType.CHEST_XRAY_PA

    @staticmethod
    def _serialize_dicom_value(val: Any) -> Any:
        """Format DICOM value to JSON-serializable standard types."""
        if isinstance(val, (pydicom.multival.MultiValue, list, tuple)):
            return [float(x) if isinstance(x, (int, float)) else str(x) for x in val]
        elif isinstance(val, (int, float, str, bool)):
            return val
        return str(val)
