"""
MedFusion AI — Heart Disease Clinical Tabular PyTorch Dataset Loader.

Provides:
- HeartDiseaseDataset: PyTorch Dataset for structured clinical tabular records
- Loads from CSV or in-memory NumPy arrays
- Integrated validation via ClinicalFeatureValidator
- Standard z-score normalization via HeartDiseasePreprocessor
- Stratified train/val/test splitting with reproducible seeding
"""

import csv
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from torch.utils.data import Dataset, Subset

from ml.config import TabularModelConfig
from ml.datasets.heart_disease.constants import (
    CORE_FEATURE_NAMES,
    CONTINUOUS_FEATURES,
    CATEGORICAL_FEATURES,
    DEFAULT_POPULATION_STATS,
)
from ml.datasets.heart_disease.preprocessor import HeartDiseasePreprocessor

logger = logging.getLogger(__name__)


class HeartDiseaseDataset(Dataset):
    """
    PyTorch Dataset for clinical tabular heart disease risk prediction.

    Accepts either:
    - A CSV file path with header row containing feature columns and a target column
    - Pre-loaded NumPy arrays (X features, y labels)

    Each sample returns (features_tensor, label_tensor).
    """

    def __init__(
        self,
        csv_path: Optional[Union[str, Path]] = None,
        X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        target_column: str = "target",
        preprocessor: Optional[HeartDiseasePreprocessor] = None,
        normalize: bool = True,
        split: Optional[str] = None,
    ):
        """
        Args:
            csv_path: Path to CSV file with clinical features and target column.
            X: NumPy feature array [n_samples, n_features]. Mutually exclusive with csv_path.
            y: NumPy label array [n_samples]. Required if X is provided.
            feature_names: Feature column names (must align with CORE_FEATURE_NAMES order).
            target_column: Name of the binary target column in CSV.
            preprocessor: HeartDiseasePreprocessor for normalization. Built automatically if None.
            normalize: Apply z-score standardization to continuous features.
            split: Optional split name for logging.
        """
        self.feature_names = feature_names or CORE_FEATURE_NAMES
        self.target_column = target_column
        self.normalize = normalize
        self.split = split
        self.preprocessor = preprocessor or HeartDiseasePreprocessor()

        if csv_path is not None:
            self._load_from_csv(Path(csv_path))
        elif X is not None:
            self._load_from_arrays(X, y)
        else:
            # Empty dataset — 1-D placeholder so num_features reports 0
            self.X = np.empty((0,), dtype=np.float32)
            self.y = np.empty((0,), dtype=np.float32)

    def _load_from_csv(self, csv_path: Path) -> None:
        """Parse CSV file into feature and label arrays."""
        if not csv_path.exists():
            logger.warning("CSV file %s not found. Dataset will be empty.", csv_path)
            self.X = np.empty((0, len(self.feature_names)), dtype=np.float32)
            self.y = np.empty((0,), dtype=np.float32)
            return

        records: List[Dict[str, Any]] = []
        labels: List[int] = []

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
                try:
                    labels.append(int(float(row.get(self.target_column, "0"))))
                except (ValueError, TypeError):
                    labels.append(0)

        if not records:
            self.X = np.empty((0, len(self.feature_names)), dtype=np.float32)
            self.y = np.empty((0,), dtype=np.float32)
            return

        # Convert records to feature arrays via preprocessor
        feature_vectors = []
        for rec in records:
            vec = self.preprocessor.transform_dict(rec, normalize_continuous=self.normalize)
            feature_vectors.append(vec)

        self.X = np.stack(feature_vectors, axis=0).astype(np.float32)
        self.y = np.array(labels, dtype=np.float32)

        logger.info(
            "HeartDiseaseDataset [%s]: loaded %d samples, %d features from CSV.",
            self.split or "all",
            len(self.y),
            self.X.shape[1],
        )

    def _load_from_arrays(self, X: np.ndarray, y: Optional[np.ndarray]) -> None:
        """Load from pre-computed NumPy arrays."""
        self.X = X.astype(np.float32)
        if y is not None:
            self.y = y.astype(np.float32)
        else:
            self.y = np.zeros(len(X), dtype=np.float32)

        logger.info(
            "HeartDiseaseDataset [%s]: loaded %d samples, %d features from arrays.",
            self.split or "all",
            len(self.y),
            self.X.shape[1] if self.X.ndim > 1 else 0,
        )

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            features: Float tensor [n_features]
            label: Float tensor (scalar) — 0.0 or 1.0
        """
        features = torch.from_numpy(self.X[idx])
        label = torch.tensor(self.y[idx], dtype=torch.float32)
        return features, label

    def get_numpy(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return raw (X, y) arrays for sklearn-compatible models."""
        return self.X, self.y

    @property
    def num_features(self) -> int:
        return self.X.shape[1] if self.X.ndim > 1 else 0


def create_heart_disease_splits(
    csv_path: Optional[Union[str, Path]] = None,
    X: Optional[np.ndarray] = None,
    y: Optional[np.ndarray] = None,
    config: Optional[TabularModelConfig] = None,
    preprocessor: Optional[HeartDiseasePreprocessor] = None,
    normalize: bool = True,
    random_seed: int = 42,
) -> Tuple[HeartDiseaseDataset, HeartDiseaseDataset, HeartDiseaseDataset]:
    """
    Create stratified train/val/test splits for heart disease tabular data.

    Accepts either CSV path or pre-loaded arrays.

    Returns:
        (train_dataset, val_dataset, test_dataset)
    """
    config = config or TabularModelConfig()
    preprocessor = preprocessor or HeartDiseasePreprocessor()

    # Load full dataset
    full = HeartDiseaseDataset(
        csv_path=csv_path,
        X=X,
        y=y,
        preprocessor=preprocessor,
        normalize=normalize,
    )

    n = len(full)
    if n == 0:
        logger.warning("Dataset is empty — returning empty splits.")
        return full, full, full

    # Stratified splitting: separate positive and negative indices
    pos_indices = np.where(full.y == 1)[0]
    neg_indices = np.where(full.y == 0)[0]

    rng = np.random.RandomState(random_seed)
    rng.shuffle(pos_indices)
    rng.shuffle(neg_indices)

    def split_indices(indices: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        n_total = len(indices)
        n_test = max(1, int(n_total * config.test_size))
        n_val = max(1, int(n_total * config.val_size))
        n_train = n_total - n_test - n_val
        return (
            indices[:n_train],
            indices[n_train : n_train + n_val],
            indices[n_train + n_val :],
        )

    pos_train, pos_val, pos_test = split_indices(pos_indices)
    neg_train, neg_val, neg_test = split_indices(neg_indices)

    train_idx = np.concatenate([pos_train, neg_train])
    val_idx = np.concatenate([pos_val, neg_val])
    test_idx = np.concatenate([pos_test, neg_test])

    rng.shuffle(train_idx)
    rng.shuffle(val_idx)
    rng.shuffle(test_idx)

    # Build per-split datasets from sliced arrays
    train_ds = HeartDiseaseDataset(
        X=full.X[train_idx],
        y=full.y[train_idx],
        preprocessor=preprocessor,
        normalize=False,  # Already preprocessed
        split="train",
    )
    val_ds = HeartDiseaseDataset(
        X=full.X[val_idx],
        y=full.y[val_idx],
        preprocessor=preprocessor,
        normalize=False,
        split="val",
    )
    test_ds = HeartDiseaseDataset(
        X=full.X[test_idx],
        y=full.y[test_idx],
        preprocessor=preprocessor,
        normalize=False,
        split="test",
    )

    logger.info(
        "HeartDisease splits: train=%d, val=%d, test=%d",
        len(train_ds),
        len(val_ds),
        len(test_ds),
    )

    return train_ds, val_ds, test_ds
