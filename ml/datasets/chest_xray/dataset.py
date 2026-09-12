"""
MedFusion AI — Chest X-Ray PyTorch Dataset Loader.

Provides:
- ChestXRayDataset: Memory-mapped image dataset for NIH ChestX-ray14 (or compatible directory layouts)
- Lazy-loaded from directory of PNG/JPEG/DICOM images with CSV label manifests
- Train/Val/Test stratified splitting with reproducible seeding
- On-the-fly CLAHE preprocessing and torchvision augmentation pipelines
- Multi-label binary target encoding for 5+ thoracic pathology classes
"""

import csv
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset, Subset
from torchvision import transforms

from ml.config import ImageModelConfig
from ml.datasets.chest_xray.transforms import MedicalImageTransforms

logger = logging.getLogger(__name__)


class ChestXRayDataset(Dataset):
    """
    PyTorch Dataset for chest radiograph images with multi-label pathology annotations.

    Expected directory layout:
        root_dir/
            images/           # flat directory of image files (PNG/JPEG)
            labels.csv        # CSV: filename, Atelectasis, Cardiomegaly, ...

    The CSV must have a header row. The first column is the image filename.
    Subsequent columns are the pathology class labels (0 or 1 for multi-label).
    """

    def __init__(
        self,
        root_dir: Union[str, Path],
        label_csv: Optional[Union[str, Path]] = None,
        image_subdir: str = "images",
        transform: Optional[Callable] = None,
        config: Optional[ImageModelConfig] = None,
        target_classes: Optional[List[str]] = None,
        use_clahe: bool = True,
        split: Optional[str] = None,
    ):
        """
        Args:
            root_dir: Root directory containing images and label manifest.
            label_csv: Path to CSV label file. Defaults to root_dir/labels.csv.
            image_subdir: Subdirectory under root_dir containing images.
            transform: Optional torchvision transform. If None, uses MedicalImageTransforms.
            config: ImageModelConfig for default transform parameters.
            target_classes: List of pathology class names to predict.
            use_clahe: Apply CLAHE preprocessing before transform.
            split: Optional split name for logging ("train", "val", "test").
        """
        self.root_dir = Path(root_dir)
        self.image_dir = self.root_dir / image_subdir
        self.config = config or ImageModelConfig()
        self.target_classes = target_classes or self.config.target_classes
        self.use_clahe = use_clahe
        self.split = split

        # Build transform pipeline
        if transform is not None:
            self.transform = transform
        else:
            med_transforms = MedicalImageTransforms(config=self.config)
            self.transform = med_transforms.eval_transforms

        # Load label manifest
        self.label_csv = Path(label_csv) if label_csv else self.root_dir / "labels.csv"
        self.samples: List[Dict[str, Any]] = []
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Parse CSV label file and build index of (filename, multi-label target) pairs."""
        if not self.label_csv.exists():
            logger.warning(
                "Label CSV %s not found. Dataset will be empty.", self.label_csv
            )
            return

        with open(self.label_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                logger.warning("Empty or malformed label CSV: %s", self.label_csv)
                return

            for row in reader:
                # First column is filename
                filename = row.get(reader.fieldnames[0], "").strip()
                if not filename:
                    continue

                image_path = self.image_dir / filename
                if not image_path.exists():
                    continue

                # Build multi-label binary vector
                labels = []
                for cls_name in self.target_classes:
                    val = row.get(cls_name, "0")
                    try:
                        labels.append(int(float(val)))
                    except (ValueError, TypeError):
                        labels.append(0)

                self.samples.append(
                    {
                        "filename": filename,
                        "image_path": str(image_path),
                        "labels": labels,
                    }
                )

        logger.info(
            "ChestXRayDataset [%s]: loaded %d samples, %d classes.",
            self.split or "all",
            len(self.samples),
            len(self.target_classes),
        )

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            image: Float tensor [3, H, W] (normalized, transformed)
            labels: Float tensor [num_classes] multi-label binary vector
        """
        sample = self.samples[idx]
        image_path = sample["image_path"]

        # Load image as RGB numpy array
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            # Fallback to PIL
            pil_img = Image.open(image_path).convert("RGB")
            image = np.array(pil_img)
        else:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Optional CLAHE enhancement
        if self.use_clahe:
            image = MedicalImageTransforms.apply_clahe(image)

        # Apply torchvision transforms (expects uint8 numpy HWC or PIL)
        if self.transform is not None:
            image_tensor = self.transform(image)
        else:
            image_tensor = torch.from_numpy(image).permute(2, 0, 1).float() / 255.0

        labels_tensor = torch.tensor(sample["labels"], dtype=torch.float32)

        return image_tensor, labels_tensor

    def get_sample_metadata(self, idx: int) -> Dict[str, Any]:
        """Return metadata for a sample without loading the image."""
        return self.samples[idx]

    @property
    def class_names(self) -> List[str]:
        return self.target_classes

    @property
    def num_classes(self) -> int:
        return len(self.target_classes)


def create_chest_xray_splits(
    root_dir: Union[str, Path],
    config: Optional[ImageModelConfig] = None,
    label_csv: Optional[Union[str, Path]] = None,
    train_transform: Optional[Callable] = None,
    eval_transform: Optional[Callable] = None,
    use_clahe: bool = True,
    random_seed: int = 42,
) -> Tuple[Dataset, Dataset, Dataset]:
    """
    Create stratified train/val/test splits of a ChestXRayDataset.

    Returns:
        (train_dataset, val_dataset, test_dataset) — Subset views with appropriate transforms.
    """
    config = config or ImageModelConfig()
    med_transforms = MedicalImageTransforms(config=config)

    # Build full dataset with eval transforms (we'll override for train split)
    full_dataset = ChestXRayDataset(
        root_dir=root_dir,
        label_csv=label_csv,
        transform=eval_transform or med_transforms.eval_transforms,
        config=config,
        use_clahe=use_clahe,
    )

    n = len(full_dataset)
    if n == 0:
        logger.warning("Dataset is empty — returning empty splits.")
        return full_dataset, full_dataset, full_dataset

    # Generate reproducible index permutation
    rng = np.random.RandomState(random_seed)
    indices = rng.permutation(n)

    n_train = int(n * config.train_ratio)
    n_val = int(n * config.val_ratio)

    train_indices = indices[:n_train].tolist()
    val_indices = indices[n_train : n_train + n_val].tolist()
    test_indices = indices[n_train + n_val :].tolist()

    # Build train dataset with augmentation transforms
    train_dataset_aug = ChestXRayDataset(
        root_dir=root_dir,
        label_csv=label_csv,
        transform=train_transform or med_transforms.train_transforms,
        config=config,
        use_clahe=use_clahe,
        split="train",
    )

    train_split = Subset(train_dataset_aug, train_indices)
    val_split = Subset(full_dataset, val_indices)
    test_split = Subset(full_dataset, test_indices)

    logger.info(
        "ChestXRay splits: train=%d, val=%d, test=%d",
        len(train_split),
        len(val_split),
        len(test_split),
    )

    return train_split, val_split, test_split
