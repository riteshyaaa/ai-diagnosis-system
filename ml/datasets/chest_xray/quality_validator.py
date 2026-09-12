"""
MedFusion AI — Medical Image Quality Assurance & Validation.

Calculates quantitative quality metrics and validates chest radiographs for:
- Degenerate / blank / all-black / all-white image detection
- Dynamic range and contrast variance
- Edge sharpness (Laplacian variance)
- Anatomical aspect ratio plausibility
- Composite diagnostic quality score (0.0 - 1.0)
"""

from dataclasses import dataclass, field
from typing import List, Tuple
import cv2
import numpy as np


@dataclass
class ImageQualityReport:
    """Quantitative quality assessment for an ingested radiograph."""
    is_valid: bool
    quality_score: float  # 0.0 (unusable) to 1.0 (optimal)
    width: int
    height: int
    aspect_ratio: float
    mean_intensity: float  # 0-255
    contrast_std: float  # standard deviation of pixel intensities
    sharpness_score: float  # Laplacian variance
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ImageQualityValidator:
    """Validates and scores medical radiograph quality prior to inference."""

    MIN_DIMENSION = 128
    MIN_CONTRAST_STD = 8.0
    MIN_MEAN_INTENSITY = 5.0
    MAX_MEAN_INTENSITY = 250.0
    MIN_ASPECT_RATIO = 0.25
    MAX_ASPECT_RATIO = 4.0
    MIN_SHARPNESS_LAPLACIAN = 15.0

    @classmethod
    def validate_image(cls, image_rgb: np.ndarray) -> ImageQualityReport:
        """
        Perform comprehensive quality and plausibility checks on RGB radiograph.
        image_rgb: (H, W, 3) uint8 numpy array.
        """
        issues: List[str] = []
        warnings: List[str] = []

        height, width = image_rgb.shape[:2]
        aspect_ratio = float(width) / float(height) if height > 0 else 0.0

        # Convert to single channel grayscale for metric calculation
        if len(image_rgb.shape) == 3 and image_rgb.shape[2] == 3:
            gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
        else:
            gray = image_rgb

        mean_intensity = float(np.mean(gray))
        contrast_std = float(np.std(gray))

        # Sharpness via Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness_score = float(laplacian.var())

        # 1. Dimension check
        if width < cls.MIN_DIMENSION or height < cls.MIN_DIMENSION:
            issues.append(
                f"Image resolution ({width}x{height}) is below minimum clinical threshold ({cls.MIN_DIMENSION}x{cls.MIN_DIMENSION})."
            )

        # 2. Aspect ratio check
        if aspect_ratio < cls.MIN_ASPECT_RATIO or aspect_ratio > cls.MAX_ASPECT_RATIO:
            issues.append(
                f"Extreme aspect ratio ({aspect_ratio:.2f}) is atypical for chest radiography."
            )

        # 3. Degenerate image check (blank / flat)
        if contrast_std < cls.MIN_CONTRAST_STD:
            issues.append(
                f"Severely low contrast (std={contrast_std:.2f}). Image appears flat, blank, or corrupted."
            )

        # 4. Exposure checks
        if mean_intensity < cls.MIN_MEAN_INTENSITY:
            issues.append(
                f"Severe underexposure (mean={mean_intensity:.2f}). Image is nearly completely dark."
            )
        elif mean_intensity > cls.MAX_MEAN_INTENSITY:
            issues.append(
                f"Severe overexposure (mean={mean_intensity:.2f}). Image is washed out / saturated."
            )
        elif mean_intensity < 20.0:
            warnings.append("Low overall brightness; subtle lung opacities may be obscured.")
        elif mean_intensity > 230.0:
            warnings.append("High overall brightness; cardiac borders may be washed out.")

        # 5. Sharpness check
        if sharpness_score < cls.MIN_SHARPNESS_LAPLACIAN:
            warnings.append("Low edge sharpness detected; image may be motion-blurred or out of focus.")

        # Compute composite quality score (0.0 to 1.0)
        # Factors: contrast (std 0-80), sharpness (0-500), mean exposure optimality (target ~110-140)
        contrast_component = min(1.0, contrast_std / 50.0)
        sharpness_component = min(1.0, sharpness_score / 200.0)
        exposure_dist = abs(mean_intensity - 128.0) / 128.0
        exposure_component = max(0.0, 1.0 - exposure_dist)

        quality_score = float(0.4 * contrast_component + 0.3 * sharpness_component + 0.3 * exposure_component)

        if issues:
            is_valid = False
            quality_score = min(quality_score, 0.3)
        else:
            is_valid = True

        return ImageQualityReport(
            is_valid=is_valid,
            quality_score=round(quality_score, 4),
            width=width,
            height=height,
            aspect_ratio=round(aspect_ratio, 4),
            mean_intensity=round(mean_intensity, 2),
            contrast_std=round(contrast_std, 2),
            sharpness_score=round(sharpness_score, 2),
            issues=issues,
            warnings=warnings,
        )
