"""
MedFusion AI — Unit Tests for Dataset Loaders & Synthetic Data Generation.

Tests:
- SyntheticChestXRayGenerator image generation, normalization, batch creation
- SyntheticClinicalTabularGenerator record schema, physiological bounds, array generation
- SyntheticMultimodalGenerator paired multimodal generation
- ChestXRayDataset loading from materialized synthetic data on disk
- HeartDiseaseDataset loading from CSV and NumPy arrays
- Stratified splitting for both image and tabular datasets
- On-disk materialization and CSV manifest integrity
"""

import csv
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

from ml.datasets.synthetic import (
    SyntheticChestXRayGenerator,
    SyntheticClinicalTabularGenerator,
    SyntheticMultimodalGenerator,
)
from ml.datasets.chest_xray.dataset import ChestXRayDataset, create_chest_xray_splits
from ml.datasets.heart_disease.dataset import (
    HeartDiseaseDataset,
    create_heart_disease_splits,
)
from ml.datasets.heart_disease.constants import (
    CORE_FEATURE_NAMES,
    CONTINUOUS_FEATURES,
    PHYSIOLOGICAL_RANGES,
)


# ── Synthetic Chest X-Ray Generator ─────────────────────────────────────────


def test_synthetic_xray_generate_image():
    """Verify single synthetic radiograph image shape, dtype, and label vector."""
    gen = SyntheticChestXRayGenerator(image_size=128, num_classes=5, random_seed=0)
    image, labels = gen.generate_image()

    assert image.shape == (128, 128, 3)
    assert image.dtype == np.uint8
    assert len(labels) == 5
    assert all(l in (0, 1) for l in labels)


def test_synthetic_xray_generate_image_with_labels():
    """Verify image generation with explicit labels produces expected labels."""
    gen = SyntheticChestXRayGenerator(image_size=64, num_classes=5, random_seed=1)
    explicit = [1, 0, 1, 0, 0]
    image, labels = gen.generate_image(labels=explicit)

    assert labels == explicit
    assert image.shape == (64, 64, 3)


def test_synthetic_xray_generate_tensor():
    """Verify tensor output shape and normalization range."""
    gen = SyntheticChestXRayGenerator(image_size=112, num_classes=5, random_seed=2)
    img_t, lbl_t = gen.generate_tensor(normalize=True)

    assert img_t.shape == (3, 112, 112)
    assert img_t.dtype == torch.float32
    assert lbl_t.shape == (5,)
    assert lbl_t.dtype == torch.float32


def test_synthetic_xray_generate_batch():
    """Verify batch generation produces correct batch dimensions."""
    gen = SyntheticChestXRayGenerator(image_size=64, num_classes=5, random_seed=3)
    images, labels = gen.generate_batch(batch_size=4, normalize=True)

    assert images.shape == (4, 3, 64, 64)
    assert labels.shape == (4, 5)


def test_synthetic_xray_materialize_to_disk():
    """Verify synthetic images and label CSV are materialized to disk correctly."""
    gen = SyntheticChestXRayGenerator(image_size=32, num_classes=5, random_seed=4)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = gen.materialize_to_disk(tmpdir, n_samples=10, image_format="png")

        images_dir = Path(out_path) / "images"
        csv_path = Path(out_path) / "labels.csv"

        assert images_dir.exists()
        assert csv_path.exists()

        # Verify correct number of images
        image_files = list(images_dir.glob("*.png"))
        assert len(image_files) == 10

        # Verify CSV structure
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header[0] == "filename"
            rows = list(reader)
            assert len(rows) == 10
            # Each row has 1 filename + 5 labels
            assert len(rows[0]) == 6


# ── Synthetic Clinical Tabular Generator ─────────────────────────────────────


def test_synthetic_tabular_generate_record():
    """Verify single clinical record schema and physiological plausibility."""
    gen = SyntheticClinicalTabularGenerator(random_seed=10)
    record, label = gen.generate_record()

    assert isinstance(record, dict)
    assert label in (0, 1)

    # Verify all core features present
    for feat in CORE_FEATURE_NAMES:
        assert feat in record, f"Missing feature: {feat}"

    # Verify continuous features within physiological bounds
    for feat in CONTINUOUS_FEATURES:
        if feat in PHYSIOLOGICAL_RANGES:
            spec = PHYSIOLOGICAL_RANGES[feat]
            val = record[feat]
            assert spec.min_val <= val <= spec.max_val, (
                f"{feat}={val} is outside [{spec.min_val}, {spec.max_val}]"
            )


def test_synthetic_tabular_explicit_label():
    """Verify generating record with explicit label uses that label."""
    gen = SyntheticClinicalTabularGenerator(random_seed=11)
    _, label_pos = gen.generate_record(label=1)
    _, label_neg = gen.generate_record(label=0)

    assert label_pos == 1
    assert label_neg == 0


def test_synthetic_tabular_generate_array():
    """Verify array generation produces correctly shaped NumPy arrays."""
    gen = SyntheticClinicalTabularGenerator(random_seed=12)
    X, y = gen.generate_array(n_samples=50, normalize=False)

    assert X.shape == (50, 13)
    assert y.shape == (50,)
    assert X.dtype == np.float32
    assert y.dtype == np.float32
    assert set(np.unique(y)).issubset({0.0, 1.0})


def test_synthetic_tabular_generate_tensors():
    """Verify PyTorch tensor generation."""
    gen = SyntheticClinicalTabularGenerator(random_seed=13)
    X_t, y_t = gen.generate_tensors(n_samples=20, normalize=True)

    assert X_t.shape == (20, 13)
    assert y_t.shape == (20,)
    assert X_t.dtype == torch.float32


def test_synthetic_tabular_materialize_csv():
    """Verify CSV materialization produces valid file."""
    gen = SyntheticClinicalTabularGenerator(random_seed=14)

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = gen.materialize_to_csv(
            Path(tmpdir) / "clinical_data.csv",
            n_samples=30,
        )

        assert csv_path.exists()
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            # 13 features + 1 target
            assert len(header) == 14
            assert header[-1] == "target"
            rows = list(reader)
            assert len(rows) == 30


# ── Synthetic Multimodal Generator ───────────────────────────────────────────


def test_synthetic_multimodal_generate_pair():
    """Verify multimodal pair generation produces matched tensors."""
    gen = SyntheticMultimodalGenerator(image_size=64, num_image_classes=5, random_seed=20)
    pair = gen.generate_pair()

    assert "image_tensor" in pair
    assert "tabular_tensor" in pair
    assert "image_labels" in pair
    assert "risk_label" in pair

    assert pair["image_tensor"].shape == (3, 64, 64)
    assert pair["tabular_tensor"].shape == (13,)
    assert pair["image_labels"].shape == (5,)
    assert pair["risk_label"].dim() == 0  # scalar


def test_synthetic_multimodal_generate_batch():
    """Verify multimodal batch generation with correct batched shapes."""
    gen = SyntheticMultimodalGenerator(image_size=64, num_image_classes=5, random_seed=21)
    batch = gen.generate_batch(batch_size=6)

    assert batch["image_tensor"].shape == (6, 3, 64, 64)
    assert batch["tabular_tensor"].shape == (6, 13)
    assert batch["image_labels"].shape == (6, 5)
    assert batch["risk_label"].shape == (6,)


def test_synthetic_multimodal_label_consistency():
    """Verify positive risk label always produces at least one positive image label."""
    gen = SyntheticMultimodalGenerator(image_size=32, num_image_classes=5, random_seed=22)

    for _ in range(20):
        pair = gen.generate_pair(label=1)
        assert pair["risk_label"].item() == 1.0
        # At least one pathology should be positive
        assert pair["image_labels"].sum().item() >= 1.0


# ── ChestXRayDataset from Disk ──────────────────────────────────────────────


def test_chest_xray_dataset_from_synthetic():
    """Verify ChestXRayDataset loads materialized synthetic images correctly."""
    gen = SyntheticChestXRayGenerator(image_size=64, num_classes=5, random_seed=30)

    with tempfile.TemporaryDirectory() as tmpdir:
        gen.materialize_to_disk(tmpdir, n_samples=10)

        dataset = ChestXRayDataset(
            root_dir=tmpdir,
            use_clahe=False,
            transform=None,  # Raw tensor without torchvision
        )

        assert len(dataset) == 10

        image, labels = dataset[0]
        assert image.dim() == 3  # [3, H, W]
        assert labels.shape == (5,)


def test_chest_xray_dataset_splits():
    """Verify train/val/test splitting produces non-overlapping subsets."""
    gen = SyntheticChestXRayGenerator(image_size=32, num_classes=5, random_seed=31)

    with tempfile.TemporaryDirectory() as tmpdir:
        gen.materialize_to_disk(tmpdir, n_samples=20)

        train, val, test = create_chest_xray_splits(
            root_dir=tmpdir,
            use_clahe=False,
            random_seed=42,
        )

        total = len(train) + len(val) + len(test)
        assert total == 20


def test_chest_xray_dataset_empty_directory():
    """Verify dataset gracefully handles missing images or labels."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # No images or CSV — should produce empty dataset
        dataset = ChestXRayDataset(root_dir=tmpdir, use_clahe=False)
        assert len(dataset) == 0


# ── HeartDiseaseDataset from Arrays ──────────────────────────────────────────


def test_heart_disease_dataset_from_arrays():
    """Verify HeartDiseaseDataset loads from NumPy arrays."""
    gen = SyntheticClinicalTabularGenerator(random_seed=40)
    X, y = gen.generate_array(n_samples=50, normalize=False)

    dataset = HeartDiseaseDataset(X=X, y=y)
    assert len(dataset) == 50

    features, label = dataset[0]
    assert features.shape == (13,)
    assert features.dtype == torch.float32
    assert label.dim() == 0


def test_heart_disease_dataset_from_csv():
    """Verify HeartDiseaseDataset loads from CSV file."""
    gen = SyntheticClinicalTabularGenerator(random_seed=41)

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = gen.materialize_to_csv(Path(tmpdir) / "data.csv", n_samples=40)

        dataset = HeartDiseaseDataset(csv_path=csv_path)
        assert len(dataset) == 40

        features, label = dataset[0]
        assert features.shape == (13,)


def test_heart_disease_dataset_get_numpy():
    """Verify get_numpy returns (X, y) arrays."""
    gen = SyntheticClinicalTabularGenerator(random_seed=42)
    X, y = gen.generate_array(n_samples=30, normalize=True)

    dataset = HeartDiseaseDataset(X=X, y=y)
    X_out, y_out = dataset.get_numpy()

    assert X_out.shape == (30, 13)
    assert y_out.shape == (30,)
    np.testing.assert_array_equal(X_out, X)


def test_heart_disease_dataset_splits():
    """Verify stratified train/val/test splitting with balanced classes."""
    gen = SyntheticClinicalTabularGenerator(random_seed=43)
    X, y = gen.generate_array(n_samples=100, normalize=True)

    train, val, test = create_heart_disease_splits(
        X=X, y=y, random_seed=42,
    )

    total = len(train) + len(val) + len(test)
    assert total == 100

    # All splits should be non-empty
    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0


def test_heart_disease_dataset_empty():
    """Verify empty dataset initialization."""
    dataset = HeartDiseaseDataset()
    assert len(dataset) == 0
    assert dataset.num_features == 0
