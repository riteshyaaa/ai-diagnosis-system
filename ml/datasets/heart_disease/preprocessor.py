"""
MedFusion AI — Clinical Tabular Preprocessing & Transformation Pipeline.

Transforms raw clinical parameters into model-ready tensors and matrices:
- Standard scaling of continuous features (z-score standardization with population stats)
- Categorical encoding (One-Hot or Dense numeric encoding)
- Multi-framework tensor output: PyTorch `torch.FloatTensor` and NumPy array
- State persistence (mean, std, feature order) to ensure reproducible online inference
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import torch

from ml.datasets.heart_disease.constants import (
    CATEGORICAL_FEATURES,
    CONTINUOUS_FEATURES,
    CORE_FEATURE_NAMES,
    DEFAULT_POPULATION_STATS,
)


class HeartDiseasePreprocessor:
    """Preprocesses and standardizes clinical tabular records for inference and training."""

    def __init__(self, stats: Optional[Dict[str, Dict[str, float]]] = None):
        self.stats = stats or DEFAULT_POPULATION_STATS
        self.feature_names = CORE_FEATURE_NAMES
        self.continuous_features = CONTINUOUS_FEATURES
        self.categorical_features = CATEGORICAL_FEATURES

    def transform_dict(
        self,
        record: Dict[str, Any],
        normalize_continuous: bool = True,
    ) -> np.ndarray:
        """
        Convert a single clinical record dictionary into a 1D NumPy float32 feature array.
        Orders features according to `CORE_FEATURE_NAMES`.
        """
        features: List[float] = []

        for feat in self.feature_names:
            val = record.get(feat)
            if val is None:
                # Fallback to cohort median
                if feat in self.stats:
                    val = self.stats[feat]["median"]
                else:
                    val = 0.0

            val = float(val)

            # Apply standard scaling to continuous features
            if normalize_continuous and feat in self.continuous_features:
                stat = self.stats.get(feat, {"mean": 0.0, "std": 1.0})
                mean = stat["mean"]
                std = stat["std"] if stat["std"] > 1e-6 else 1.0
                val = (val - mean) / std

            features.append(val)

        return np.array(features, dtype=np.float32)

    def transform_to_tensor(
        self,
        record_or_list: Union[Dict[str, Any], List[Dict[str, Any]]],
        normalize_continuous: bool = True,
    ) -> torch.Tensor:
        """
        Convert a single record or list of records into a 2D PyTorch FloatTensor [batch_size, num_features].
        """
        if isinstance(record_or_list, dict):
            records = [record_or_list]
        else:
            records = record_or_list

        vectors = [
            self.transform_dict(rec, normalize_continuous=normalize_continuous)
            for rec in records
        ]
        stacked = np.stack(vectors, axis=0)
        return torch.from_numpy(stacked)

    def transform_one_hot(self, record: Dict[str, Any]) -> np.ndarray:
        """
        Generate expanded one-hot representation for categorical features (useful for linear/neural models).
        Continuous features: standardized [5 features]
        sex: [2]
        chest_pain_type (0-3): [4]
        fasting_bs (0-1): [2]
        resting_ecg (0-2): [3]
        exercise_angina (0-1): [2]
        st_slope (0-2): [3]
        num_major_vessels (0-3): [4]
        thalassemia (1-3): [3]
        Total: 5 + 2 + 4 + 2 + 3 + 2 + 3 + 4 + 3 = 28 features
        """
        dense_feats: List[float] = []

        # Standardized continuous features
        for feat in self.continuous_features:
            val = float(record.get(feat, self.stats.get(feat, {}).get("median", 0.0)))
            stat = self.stats.get(feat, {"mean": 0.0, "std": 1.0})
            norm_val = (val - stat["mean"]) / (stat["std"] if stat["std"] > 1e-6 else 1.0)
            dense_feats.append(norm_val)

        # One-hot helper
        def one_hot(val: int, num_classes: int, offset: int = 0) -> List[float]:
            vec = [0.0] * num_classes
            idx = int(val) - offset
            if 0 <= idx < num_classes:
                vec[idx] = 1.0
            return vec

        dense_feats.extend(one_hot(int(record.get("sex", 0)), 2))
        dense_feats.extend(one_hot(int(record.get("chest_pain_type", 0)), 4))
        dense_feats.extend(one_hot(int(record.get("fasting_bs", 0)), 2))
        dense_feats.extend(one_hot(int(record.get("resting_ecg", 0)), 3))
        dense_feats.extend(one_hot(int(record.get("exercise_angina", 0)), 2))
        dense_feats.extend(one_hot(int(record.get("st_slope", 0)), 3))
        dense_feats.extend(one_hot(int(record.get("num_major_vessels", 0)), 4))
        dense_feats.extend(one_hot(int(record.get("thalassemia", 1)), 3, offset=1))

        return np.array(dense_feats, dtype=np.float32)

    def save_stats(self, file_path: Union[str, Path]) -> None:
        """Persist normalization statistics to JSON file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)

    @classmethod
    def load_stats(cls, file_path: Union[str, Path]) -> "HeartDiseasePreprocessor":
        """Instantiate preprocessor from persisted JSON statistics."""
        with open(file_path, "r", encoding="utf-8") as f:
            stats = json.load(f)
        return cls(stats=stats)
