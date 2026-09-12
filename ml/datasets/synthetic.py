"""
MedFusion AI — Synthetic Data Generation Pipelines.

Provides clinically realistic synthetic data generators for development, testing,
and data augmentation workflows. Generates:

- Synthetic chest X-ray image tensors with controllable pathology simulation
- Synthetic clinical tabular records matching UCI Heart Disease feature schema
- Paired multimodal datasets (image + tabular) for fusion model development
- On-disk materialization with CSV label manifests for end-to-end pipeline testing

All synthetic data is clearly marked as generated and MUST NOT be used for
clinical decision-making. These generators exist solely to support development,
unit testing, and model architecture validation.
"""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import torch

from ml.config import ImageModelConfig
from ml.datasets.heart_disease.constants import (
    CORE_FEATURE_NAMES,
    CONTINUOUS_FEATURES,
    CATEGORICAL_FEATURES,
    DEFAULT_POPULATION_STATS,
    PHYSIOLOGICAL_RANGES,
)

logger = logging.getLogger(__name__)


class SyntheticChestXRayGenerator:
    """
    Generates synthetic chest radiograph images for testing.

    Produces grayscale-to-RGB images with Gaussian noise, gradient fields,
    and optional circular "lesion" overlays to simulate pathological findings.
    NOT clinically valid — for pipeline testing only.
    """

    def __init__(
        self,
        image_size: int = 224,
        num_classes: int = 5,
        target_classes: Optional[List[str]] = None,
        random_seed: int = 42,
    ):
        self.image_size = image_size
        self.num_classes = num_classes
        self.target_classes = target_classes or ImageModelConfig().target_classes
        self.rng = np.random.RandomState(random_seed)

    def generate_image(
        self,
        labels: Optional[List[int]] = None,
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Generate a single synthetic radiograph image.

        Args:
            labels: Optional multi-label binary vector. If None, randomly generated.

        Returns:
            (image_rgb_uint8, labels) — image is [H, W, 3] uint8, labels is list of 0/1.
        """
        h, w = self.image_size, self.image_size

        # Base: gradient field simulating mediastinal density, with Gaussian noise
        y_coords = np.linspace(0.3, 0.7, h)[:, np.newaxis] * np.ones((1, w))
        base = (y_coords * 255).astype(np.float32)

        # Add Gaussian noise for tissue texture
        noise = self.rng.normal(0, 25, size=(h, w)).astype(np.float32)
        base = np.clip(base + noise, 0, 255)

        # Generate labels if not provided
        if labels is None:
            labels = self.rng.randint(0, 2, size=self.num_classes).tolist()

        # Simulate pathology findings with circular overlays
        for cls_idx, present in enumerate(labels):
            if present:
                # Random position and radius for lesion simulation
                cx = self.rng.randint(w // 4, 3 * w // 4)
                cy = self.rng.randint(h // 4, 3 * h // 4)
                radius = self.rng.randint(10, max(12, w // 6))
                intensity = self.rng.uniform(0.4, 0.8) * 255

                # Draw filled circle with blending
                yy, xx = np.ogrid[:h, :w]
                mask = ((xx - cx) ** 2 + (yy - cy) ** 2) <= radius ** 2
                base[mask] = np.clip(base[mask] * 0.5 + intensity * 0.5, 0, 255)

        image_gray = base.astype(np.uint8)
        # Convert to 3-channel RGB
        image_rgb = cv2.cvtColor(image_gray, cv2.COLOR_GRAY2RGB)

        return image_rgb, labels

    def generate_tensor(
        self,
        labels: Optional[List[int]] = None,
        normalize: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Generate a synthetic image as a PyTorch tensor.

        Returns:
            (image_tensor, labels_tensor) — image [3, H, W] float, labels [num_classes] float.
        """
        image_rgb, labels_list = self.generate_image(labels=labels)

        # Convert to float tensor: [H, W, 3] -> [3, H, W]
        image_tensor = torch.from_numpy(image_rgb).permute(2, 0, 1).float() / 255.0

        if normalize:
            # ImageNet normalization
            mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
            std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            image_tensor = (image_tensor - mean) / std

        labels_tensor = torch.tensor(labels_list, dtype=torch.float32)
        return image_tensor, labels_tensor

    def generate_batch(
        self,
        batch_size: int = 8,
        normalize: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Generate a batch of synthetic radiograph tensors.

        Returns:
            (images, labels) — images [B, 3, H, W], labels [B, num_classes].
        """
        images, labels = [], []
        for _ in range(batch_size):
            img_t, lbl_t = self.generate_tensor(normalize=normalize)
            images.append(img_t)
            labels.append(lbl_t)
        return torch.stack(images), torch.stack(labels)

    def materialize_to_disk(
        self,
        output_dir: Union[str, Path],
        n_samples: int = 100,
        image_format: str = "png",
    ) -> Path:
        """
        Write synthetic images and a CSV label manifest to disk.

        Creates:
            output_dir/
                images/       # PNG or JPEG image files
                labels.csv    # CSV manifest with filename and multi-label columns

        Returns:
            Path to the output directory.
        """
        output_path = Path(output_dir)
        images_dir = output_path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        csv_path = output_path / "labels.csv"
        header = ["filename"] + self.target_classes

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)

            for i in range(n_samples):
                image_rgb, labels = self.generate_image()
                filename = f"synth_{i:05d}.{image_format}"
                filepath = images_dir / filename

                # Save image
                image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                cv2.imwrite(str(filepath), image_bgr)

                # Write CSV row
                writer.writerow([filename] + labels)

        logger.info(
            "Materialized %d synthetic chest X-rays to %s", n_samples, output_path
        )
        return output_path


class SyntheticClinicalTabularGenerator:
    """
    Generates synthetic clinical tabular records matching UCI Heart Disease schema.

    Samples continuous features from Gaussian distributions derived from population
    statistics, and categorical features from plausible prior distributions.
    NOT clinically valid — for pipeline testing and model architecture validation only.
    """

    def __init__(
        self,
        feature_names: Optional[List[str]] = None,
        random_seed: int = 42,
    ):
        self.feature_names = feature_names or CORE_FEATURE_NAMES
        self.rng = np.random.RandomState(random_seed)

    def generate_record(
        self,
        label: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Generate a single synthetic clinical record as a dictionary.

        Returns:
            (record_dict, label) — dict with feature names as keys, label is 0 or 1.
        """
        record: Dict[str, Any] = {}

        # Continuous features: sample from population-derived Gaussians
        for feat in CONTINUOUS_FEATURES:
            stats = DEFAULT_POPULATION_STATS.get(feat, {"mean": 0, "std": 1})
            val = self.rng.normal(stats["mean"], stats["std"])

            # Clamp to physiological bounds
            range_spec = PHYSIOLOGICAL_RANGES.get(feat)
            if range_spec:
                val = np.clip(val, range_spec.min_val, range_spec.max_val)

            record[feat] = round(float(val), 1)

        # Categorical features: sample from plausible priors
        record["sex"] = int(self.rng.choice([0, 1], p=[0.32, 0.68]))
        record["chest_pain_type"] = int(self.rng.choice([0, 1, 2, 3], p=[0.15, 0.20, 0.30, 0.35]))
        record["fasting_bs"] = int(self.rng.choice([0, 1], p=[0.85, 0.15]))
        record["resting_ecg"] = int(self.rng.choice([0, 1, 2], p=[0.52, 0.33, 0.15]))
        record["exercise_angina"] = int(self.rng.choice([0, 1], p=[0.67, 0.33]))
        record["st_slope"] = int(self.rng.choice([0, 1, 2], p=[0.40, 0.35, 0.25]))
        record["num_major_vessels"] = int(self.rng.choice([0, 1, 2, 3], p=[0.55, 0.25, 0.12, 0.08]))
        record["thalassemia"] = int(self.rng.choice([1, 2, 3], p=[0.55, 0.15, 0.30]))

        # Generate label with simple risk heuristic (not clinically accurate)
        if label is None:
            risk_score = 0.0
            if record["age"] > 55:
                risk_score += 0.2
            if record["chest_pain_type"] == 3:
                risk_score += 0.15
            if record["exercise_angina"] == 1:
                risk_score += 0.15
            if record["st_depression"] > 1.5:
                risk_score += 0.15
            if record["num_major_vessels"] >= 2:
                risk_score += 0.15
            if record["thalassemia"] == 3:
                risk_score += 0.1
            risk_score = min(risk_score + self.rng.uniform(-0.15, 0.15), 1.0)
            label = 1 if risk_score > 0.5 else 0

        return record, label

    def generate_array(
        self,
        n_samples: int = 100,
        normalize: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate a NumPy array of synthetic clinical feature vectors and labels.

        Args:
            n_samples: Number of synthetic patients.
            normalize: Apply z-score normalization to continuous features.

        Returns:
            (X, y) — X [n_samples, n_features], y [n_samples].
        """
        from ml.datasets.heart_disease.preprocessor import HeartDiseasePreprocessor

        preprocessor = HeartDiseasePreprocessor()
        X_list, y_list = [], []

        for _ in range(n_samples):
            record, label = self.generate_record()
            vec = preprocessor.transform_dict(record, normalize_continuous=normalize)
            X_list.append(vec)
            y_list.append(label)

        X = np.stack(X_list, axis=0).astype(np.float32)
        y = np.array(y_list, dtype=np.float32)

        return X, y

    def generate_tensors(
        self,
        n_samples: int = 100,
        normalize: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Generate synthetic tabular data as PyTorch tensors.

        Returns:
            (X_tensor, y_tensor) — X [n_samples, n_features], y [n_samples].
        """
        X, y = self.generate_array(n_samples=n_samples, normalize=normalize)
        return torch.from_numpy(X), torch.from_numpy(y)

    def materialize_to_csv(
        self,
        output_path: Union[str, Path],
        n_samples: int = 100,
    ) -> Path:
        """
        Write synthetic clinical records to a CSV file.

        Returns:
            Path to the written CSV file.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        header = CORE_FEATURE_NAMES + ["target"]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)

            for _ in range(n_samples):
                record, label = self.generate_record()
                row = [record.get(feat, 0) for feat in CORE_FEATURE_NAMES] + [label]
                writer.writerow(row)

        logger.info("Materialized %d synthetic clinical records to %s", n_samples, path)
        return path


class SyntheticMultimodalGenerator:
    """
    Generates matched pairs of (chest X-ray image, clinical tabular record)
    with consistent labels for multimodal fusion model development.
    """

    def __init__(
        self,
        image_size: int = 224,
        num_image_classes: int = 5,
        random_seed: int = 42,
    ):
        self.image_gen = SyntheticChestXRayGenerator(
            image_size=image_size,
            num_classes=num_image_classes,
            random_seed=random_seed,
        )
        self.tabular_gen = SyntheticClinicalTabularGenerator(
            random_seed=random_seed + 1,
        )
        self.rng = np.random.RandomState(random_seed)

    def generate_pair(
        self,
        label: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate a matched (image, tabular, label) triple.

        Returns:
            Dict with 'image_tensor', 'tabular_tensor', 'image_labels', 'risk_label'.
        """
        # Shared risk label
        if label is None:
            label = int(self.rng.randint(0, 2))

        # Image: multi-label (at least one positive class if label=1)
        if label == 1:
            image_labels = [0] * self.image_gen.num_classes
            n_pos = self.rng.randint(1, min(3, self.image_gen.num_classes) + 1)
            pos_indices = self.rng.choice(self.image_gen.num_classes, size=n_pos, replace=False)
            for idx in pos_indices:
                image_labels[idx] = 1
        else:
            image_labels = [0] * self.image_gen.num_classes

        image_tensor, _ = self.image_gen.generate_tensor(labels=image_labels, normalize=True)

        # Tabular
        record, _ = self.tabular_gen.generate_record(label=label)
        from ml.datasets.heart_disease.preprocessor import HeartDiseasePreprocessor
        preprocessor = HeartDiseasePreprocessor()
        tabular_vec = preprocessor.transform_dict(record, normalize_continuous=True)
        tabular_tensor = torch.from_numpy(tabular_vec)

        return {
            "image_tensor": image_tensor,       # [3, H, W]
            "tabular_tensor": tabular_tensor,    # [n_features]
            "image_labels": torch.tensor(image_labels, dtype=torch.float32),  # [num_classes]
            "risk_label": torch.tensor(label, dtype=torch.float32),           # scalar
        }

    def generate_batch(
        self,
        batch_size: int = 8,
    ) -> Dict[str, torch.Tensor]:
        """
        Generate a batch of matched multimodal pairs.

        Returns:
            Dict with batched tensors:
                'image_tensor': [B, 3, H, W]
                'tabular_tensor': [B, n_features]
                'image_labels': [B, num_classes]
                'risk_label': [B]
        """
        pairs = [self.generate_pair() for _ in range(batch_size)]
        return {
            "image_tensor": torch.stack([p["image_tensor"] for p in pairs]),
            "tabular_tensor": torch.stack([p["tabular_tensor"] for p in pairs]),
            "image_labels": torch.stack([p["image_labels"] for p in pairs]),
            "risk_label": torch.stack([p["risk_label"] for p in pairs]),
        }
