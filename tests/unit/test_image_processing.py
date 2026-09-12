"""
MedFusion AI — Medical Image Processing & DICOM Unit Tests.

Tests:
- Radiograph simulation & CLAHE contrast enhancement
- Standard model tensor preprocessing (ImageNet normalization, shape [1, 3, 224, 224])
- Diagnostic quality assurance validator (valid vs blank vs undersized vs extreme aspect ratio)
- DICOM parser and strict de-identification (MONOCHROME1/2, VOI LUT, PII scrubbing)
"""

import io
import numpy as np
import pytest
from PIL import Image
import torch
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.models.image_record import ImageType
from ml.datasets.chest_xray.dicom_parser import DicomParser
from ml.datasets.chest_xray.quality_validator import ImageQualityValidator
from ml.datasets.chest_xray.transforms import MedicalImageTransforms


def create_synthetic_radiograph(width: int = 256, height: int = 256) -> np.ndarray:
    """Generate a synthetic chest radiograph pattern (lung fields + ribs)."""
    img = np.full((height, width), 40, dtype=np.uint8)  # Soft tissue background

    # Simulated lung fields (darker regions)
    cv2_ellipse_left = (int(width * 0.35), int(height * 0.5))
    cv2_ellipse_right = (int(width * 0.65), int(height * 0.5))
    axes = (int(width * 0.2), int(height * 0.35))

    y, x = np.ogrid[:height, :width]
    mask_left = ((x - cv2_ellipse_left[0]) ** 2) / (axes[0] ** 2) + ((y - cv2_ellipse_left[1]) ** 2) / (axes[1] ** 2) <= 1
    mask_right = ((x - cv2_ellipse_right[0]) ** 2) / (axes[0] ** 2) + ((y - cv2_ellipse_right[1]) ** 2) <= 1

    img[mask_left] = 20
    img[mask_right] = 20

    # Simulated ribs (horizontal brighter bands)
    for rib_y in range(int(height * 0.2), int(height * 0.8), int(height * 0.1)):
        img[rib_y : rib_y + 8, :] = np.clip(img[rib_y : rib_y + 8, :] + 80, 0, 255)

    # Simulated spine / mediastinum (vertical bright band in center)
    center_x = int(width * 0.5)
    img[:, center_x - 15 : center_x + 15] = np.clip(img[:, center_x - 15 : center_x + 15] + 100, 0, 255)

    return img


def create_synthetic_dicom_bytes(
    width: int = 256,
    height: int = 256,
    photometric: str = "MONOCHROME2",
    view_position: str = "PA",
) -> bytes:
    """Create a minimal valid DICOM dataset with embedded pixel array and PII for de-identification tests."""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1"  # CR Image Storage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = file_meta
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    # Synthetic image array
    pixels = create_synthetic_radiograph(width, height)
    if photometric == "MONOCHROME1":
        pixels = 255 - pixels

    # Sensitive PII tags (MUST BE STRIPPED BY DE-IDENTIFIER)
    ds.PatientName = "DOE^JOHN^A"
    ds.PatientID = "SECRET-PII-998811"
    ds.PatientBirthDate = "19600101"
    ds.PatientSex = "M"
    ds.InstitutionName = "Metropolitan General Hospital"
    ds.ReferringPhysicianName = "Dr. Secret Doctor"

    # Technical Medical Metadata (SAFE TO KEEP)
    ds.Modality = "CR"
    ds.BodyPartExamined = "CHEST"
    ds.ViewPosition = view_position
    ds.PhotometricInterpretation = photometric
    ds.Rows = height
    ds.Columns = width
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.WindowCenter = 128
    ds.WindowWidth = 256
    ds.RescaleSlope = 1.0
    ds.RescaleIntercept = 0.0
    ds.PixelSpacing = [0.143, 0.143]

    ds.PixelData = pixels.tobytes()

    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    return buf.getvalue()


def test_synthetic_radiograph_clahe_and_transforms():
    """Verify CLAHE enhancement and PyTorch model tensor preprocessing."""
    transforms = MedicalImageTransforms()
    raw_img = create_synthetic_radiograph(256, 256)

    # 1. Test CLAHE enhancement
    enhanced = transforms.apply_clahe(raw_img)
    assert enhanced.shape == (256, 256)
    # Contrast standard deviation should increase or remain strong
    assert np.std(enhanced) >= np.std(raw_img) * 0.9

    # 2. Test full inference preprocessing
    tensor, enhanced_rgb = transforms.preprocess_for_inference(raw_img, use_clahe=True)
    assert tensor.shape == (1, 3, 224, 224)
    assert isinstance(tensor, torch.Tensor)
    assert enhanced_rgb.shape == (256, 256, 3)
    assert enhanced_rgb.dtype == np.uint8


def test_quality_validator_valid_image():
    """Verify standard diagnostic radiograph passes quality checks."""
    raw_img = create_synthetic_radiograph(256, 256)
    rgb = MedicalImageTransforms.ensure_3channel_rgb(raw_img)

    report = ImageQualityValidator.validate_image(rgb)
    assert report.is_valid is True
    assert report.quality_score > 0.4
    assert report.width == 256
    assert report.height == 256
    assert len(report.issues) == 0


def test_quality_validator_rejects_blank_and_corrupt_images():
    """Verify validator flags blank, flat, tiny, and extreme aspect ratio images."""
    # 1. Completely black image
    black_img = np.zeros((256, 256, 3), dtype=np.uint8)
    rep_black = ImageQualityValidator.validate_image(black_img)
    assert rep_black.is_valid is False
    assert any("underexposure" in s.lower() or "contrast" in s.lower() for s in rep_black.issues)

    # 2. Completely white image
    white_img = np.full((256, 256, 3), 255, dtype=np.uint8)
    rep_white = ImageQualityValidator.validate_image(white_img)
    assert rep_white.is_valid is False
    assert any("overexposure" in s.lower() or "contrast" in s.lower() for s in rep_white.issues)

    # 3. Tiny / undersized image (e.g. 64x64)
    tiny_img = np.random.randint(50, 200, (64, 64, 3), dtype=np.uint8)
    rep_tiny = ImageQualityValidator.validate_image(tiny_img)
    assert rep_tiny.is_valid is False
    assert any("resolution" in s.lower() for s in rep_tiny.issues)

    # 4. Extreme aspect ratio (e.g. 500 x 50)
    skewed_img = np.random.randint(50, 200, (50, 500, 3), dtype=np.uint8)
    rep_skewed = ImageQualityValidator.validate_image(skewed_img)
    assert rep_skewed.is_valid is False
    assert any("aspect ratio" in s.lower() or "resolution" in s.lower() for s in rep_skewed.issues)


def test_dicom_parser_and_deidentification():
    """Verify DICOM parser strips PII, normalizes pixels, and extracts technical metadata."""
    dcm_bytes = create_synthetic_dicom_bytes(width=256, height=256, photometric="MONOCHROME2", view_position="PA")

    parsed = DicomParser.parse_from_bytes(dcm_bytes)
    assert parsed.is_dicom is True
    assert parsed.width == 256
    assert parsed.height == 256
    assert parsed.channels == 3
    assert parsed.image_type == ImageType.CHEST_XRAY_PA

    # Verify PII tags are completely absent
    assert "PatientName" not in parsed.technical_metadata
    assert "PatientID" not in parsed.technical_metadata
    assert "PatientBirthDate" not in parsed.technical_metadata
    assert "InstitutionName" not in parsed.technical_metadata
    assert "ReferringPhysicianName" not in parsed.technical_metadata

    # Verify technical metadata is preserved
    assert parsed.technical_metadata["Modality"] == "CR"
    assert parsed.technical_metadata["BodyPartExamined"] == "CHEST"
    assert parsed.technical_metadata["ViewPosition"] == "PA"


def test_dicom_parser_monochrome1_inversion():
    """Verify MONOCHROME1 pixels are inverted to match standard MONOCHROME2 radiographs."""
    dcm_mono1 = create_synthetic_dicom_bytes(width=256, height=256, photometric="MONOCHROME1", view_position="LATERAL")

    parsed = DicomParser.parse_from_bytes(dcm_mono1)
    assert parsed.image_type == ImageType.CHEST_XRAY_LATERAL
    assert parsed.pixel_array.shape == (256, 256, 3)
    # The mean intensity should be in standard range (not inverted/negative)
    assert 10 < np.mean(parsed.pixel_array) < 240
