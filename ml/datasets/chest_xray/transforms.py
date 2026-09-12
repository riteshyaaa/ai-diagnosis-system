"""
MedFusion AI — Chest X-ray Image Preprocessing & Augmentation Transforms.

Provides standardized transform pipelines for:
- Clinical DICOM parsing, windowing (VOI LUT), and MONOCHROME1 inversion
- Contrast Limited Adaptive Histogram Equalization (CLAHE) for lung/bone contrast
- Training augmentations (rotation, affine, horizontal flip, brightness/contrast)
- Evaluation / Inference transformations (resize, tensor conversion, ImageNet normalization)
"""

from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import cv2
from PIL import Image
import torch
from torchvision import transforms

from ml.config import ImageModelConfig


class MedicalImageTransforms:
    """Medical radiograph transformations and preprocessing pipeline."""

    def __init__(self, config: Optional[ImageModelConfig] = None):
        self.config = config or ImageModelConfig()
        self.target_size = (self.config.image_size, self.config.image_size)
        self.mean = self.config.mean
        self.std = self.config.std

        # Standard PyTorch normalization transform
        self.normalize_transform = transforms.Normalize(
            mean=self.mean,
            std=self.std,
        )

        # Standard Evaluation / Inference Torchvision Pipeline
        self.eval_transforms = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize(self.target_size, interpolation=transforms.InterpolationMode.BILINEAR),
            transforms.ToTensor(),
            self.normalize_transform,
        ])

        # Training Augmentation Pipeline
        self.train_transforms = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize(self.target_size, interpolation=transforms.InterpolationMode.BILINEAR),
            transforms.RandomHorizontalFlip(p=self.config.horizontal_flip_prob),
            transforms.RandomRotation(degrees=self.config.rotation_limit),
            transforms.ColorJitter(
                brightness=self.config.brightness_limit,
                contrast=self.config.contrast_limit,
            ),
            transforms.ToTensor(),
            self.normalize_transform,
        ])

    @staticmethod
    def apply_clahe(
        image: np.ndarray,
        clip_limit: float = 2.0,
        tile_grid_size: Tuple[int, int] = (8, 8),
    ) -> np.ndarray:
        """
        Apply Contrast Limited Adaptive Histogram Equalization (CLAHE) to grayscale/RGB image.
        Enhances lung parenchyma, cardiac borders, and bone details without over-amplifying noise.
        """
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

        if len(image.shape) == 2:
            # Single channel grayscale
            return clahe.apply(image)
        elif len(image.shape) == 3:
            if image.shape[2] == 1:
                return clahe.apply(image[:, :, 0])
            elif image.shape[2] == 3:
                # Convert to LAB color space, apply CLAHE to Luminance (L) channel, convert back
                lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
                lab_planes = list(cv2.split(lab))
                lab_planes[0] = clahe.apply(lab_planes[0])
                lab = cv2.merge(lab_planes)
                return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
            elif image.shape[2] == 4:
                # RGBA -> RGB -> CLAHE
                rgb = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
                return MedicalImageTransforms.apply_clahe(rgb, clip_limit, tile_grid_size)

        return image

    @staticmethod
    def apply_windowing(
        pixel_array: np.ndarray,
        window_center: Optional[float] = None,
        window_width: Optional[float] = None,
        rescale_slope: float = 1.0,
        rescale_intercept: float = 0.0,
    ) -> np.ndarray:
        """
        Apply DICOM VOI LUT / Windowing to convert raw detector values to displayable 8-bit image.
        HU = pixel * slope + intercept
        [center - width/2, center + width/2] mapped to [0, 255]
        """
        hu_image = pixel_array.astype(np.float32) * rescale_slope + rescale_intercept

        if window_center is not None and window_width is not None and window_width > 0:
            lower = window_center - (window_width / 2.0)
            upper = window_center + (window_width / 2.0)
            windowed = np.clip(hu_image, lower, upper)
            # Normalize to 0-255 uint8
            windowed = ((windowed - lower) / (upper - lower)) * 255.0
            return windowed.astype(np.uint8)
        else:
            # Default min-max dynamic range scaling
            p_min = np.min(hu_image)
            p_max = np.max(hu_image)
            if p_max > p_min:
                scaled = ((hu_image - p_min) / (p_max - p_min)) * 255.0
            else:
                scaled = np.zeros_like(hu_image)
            return scaled.astype(np.uint8)

    @staticmethod
    def ensure_3channel_rgb(image: np.ndarray) -> np.ndarray:
        """Ensure image is formatted as 3-channel uint8 RGB numpy array (H, W, 3)."""
        if len(image.shape) == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif len(image.shape) == 3:
            if image.shape[2] == 1:
                return cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:
                return cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            elif image.shape[2] == 3:
                return image
        raise ValueError(f"Unsupported image array shape: {image.shape}")

    def preprocess_for_inference(
        self,
        image: Union[np.ndarray, Image.Image],
        use_clahe: bool = True,
    ) -> Tuple[torch.Tensor, np.ndarray]:
        """
        Full inference preprocessing:
        1. Convert to RGB uint8 numpy array
        2. Optional CLAHE enhancement
        3. Resize and ImageNet normalize -> torch.Tensor of shape (1, 3, 224, 224)
        Returns (normalized_tensor, preprocessed_rgb_uint8_array)
        """
        if isinstance(image, Image.Image):
            rgb_arr = np.array(image.convert("RGB"))
        else:
            rgb_arr = self.ensure_3channel_rgb(image)

        if use_clahe:
            enhanced_rgb = self.apply_clahe(rgb_arr)
        else:
            enhanced_rgb = rgb_arr

        # PyTorch Tensor transform: (H, W, 3) -> (3, 224, 224) -> (1, 3, 224, 224)
        tensor = self.eval_transforms(enhanced_rgb)
        tensor = tensor.unsqueeze(0)  # Add batch dimension

        return tensor, enhanced_rgb
