"""
MedFusion AI — Comprehensive Unit Tests for Training Loops, Validation Engine & MLflow Tracking.

Tests:
- Clinical evaluation metrics (BinaryMetrics, MultiLabelMetrics, ECE calibration)
- Evaluation report generation, serialization, and disk persistence
- Early stopping monitor with best-weights restoration
- Model checkpointing callback and metadata persistence
- MLflowTracker parameter, metric, and artifact logging
- ChestXRayTrainer training loop, validation, and multi-label evaluation
- TabularMLPTrainer & TreeModelTrainer with post-hoc calibration
- MultimodalFusionTrainer two-stage training loop, stage transition, and multi-task evaluation
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, TensorDataset

from ml.config import FusionModelConfig, ImageModelConfig, TabularModelConfig
from ml.evaluation.metrics import (
    BinaryMetrics,
    EvaluationReport,
    MultiLabelMetrics,
    compute_binary_metrics,
    compute_expected_calibration_error,
    compute_multilabel_metrics,
)
from ml.models.image.classifier import ChestXRayClassifier
from ml.models.tabular.neural_models import TabularRiskMLP
from ml.models.tabular.tree_models import RandomForestRiskClassifier, XGBoostRiskClassifier
from ml.models.fusion.late_fusion import MultimodalLateFusionModel
from ml.training.callbacks import EarlyStopping, ModelCheckpoint, LearningRateSchedulerCallback
from ml.training.image_trainer import ChestXRayTrainer
from ml.training.tabular_trainer import TabularMLPTrainer, TreeModelTrainer
from ml.training.fusion_trainer import MultimodalFusionTrainer
from ml.training.tracker import MLflowTracker


# ── Metrics & Evaluation Tests ──────────────────────────────────────────────


def test_compute_binary_metrics_perfect():
    """Verify metrics calculation for perfect predictions."""
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.05, 0.1, 0.9, 0.95])

    metrics = compute_binary_metrics(y_true, y_prob)

    assert metrics.auroc == 1.0
    assert metrics.accuracy == 1.0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.specificity == 1.0
    assert metrics.f1 == 1.0
    assert metrics.tp == 2
    assert metrics.tn == 2
    assert metrics.fp == 0
    assert metrics.fn == 0
    assert metrics.brier_score < 0.05


def test_compute_binary_metrics_empty():
    """Verify graceful handling of empty inputs."""
    metrics = compute_binary_metrics([], [])
    assert metrics.n_samples == 0
    assert metrics.auroc == 0.5
    assert metrics.f1 == 0.0


def test_compute_expected_calibration_error():
    """Verify ECE calculation and reliability data shape."""
    y_true = np.array([0, 0, 1, 1, 0, 1, 1, 0])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9, 0.4, 0.7, 0.85, 0.15])

    ece, rel_data = compute_expected_calibration_error(y_true, y_prob, n_bins=5)

    assert 0.0 <= ece <= 1.0
    assert "prob_true" in rel_data
    assert "prob_pred" in rel_data
    assert "bin_counts" in rel_data
    assert len(rel_data["prob_true"]) == 5


def test_compute_multilabel_metrics():
    """Verify multi-label metric aggregation across classes."""
    y_true = np.array([[1, 0, 0], [0, 1, 0], [1, 1, 1], [0, 0, 1]])
    y_probs = np.array([[0.8, 0.1, 0.2], [0.2, 0.9, 0.1], [0.7, 0.8, 0.9], [0.1, 0.2, 0.85]])
    class_names = ["Atelectasis", "Cardiomegaly", "Effusion"]

    ml_metrics = compute_multilabel_metrics(y_true, y_probs, class_names=class_names)

    assert ml_metrics.macro_auroc > 0.8
    assert ml_metrics.macro_f1 > 0.6
    assert len(ml_metrics.per_class_metrics) == 3
    assert "Cardiomegaly" in ml_metrics.per_class_metrics
    assert ml_metrics.n_samples == 4


def test_evaluation_report_serialization():
    """Verify EvaluationReport conversion to dict, JSON, and file persistence."""
    bm = compute_binary_metrics([0, 1, 1, 0], [0.1, 0.9, 0.8, 0.2])
    report = EvaluationReport(
        model_name="TestModel",
        dataset_split="test",
        task_type="binary",
        timestamp="2026-09-10T12:00:00",
        binary_metrics=bm,
    )

    data = report.to_dict()
    assert data["model_name"] == "TestModel"
    assert "binary_metrics" in data

    json_str = report.to_json()
    assert "TestModel" in json_str

    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "report.json"
        saved = report.save(out_file)
        assert saved.exists()
        with open(saved, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            assert loaded["task_type"] == "binary"


# ── Callbacks & Tracking Tests ──────────────────────────────────────────────


def test_early_stopping_trigger_and_restore():
    """Verify early stopping triggers after patience exhaustion and restores weights."""
    model = nn.Linear(5, 1)
    initial_weight = model.weight.data.clone()

    es = EarlyStopping(patience=2, mode="max", monitor="val_auroc", restore_best_weights=True)

    # Epoch 1: improvement
    stop1 = es.step(epoch=1, metric_value=0.75, model=model)
    assert not stop1
    assert es.best_epoch == 1

    # Modify weights artificially
    with torch.no_grad():
        model.weight.data.fill_(99.0)

    # Epoch 2: no improvement (counter = 1)
    stop2 = es.step(epoch=2, metric_value=0.70, model=model)
    assert not stop2
    assert es.counter == 1

    # Epoch 3: no improvement (counter = 2 -> trigger stop)
    stop3 = es.step(epoch=3, metric_value=0.71, model=model)
    assert stop3
    assert es.early_stop

    # Model weights should be restored from epoch 1 (initial weights, not 99.0)
    assert not torch.allclose(model.weight.data, torch.tensor(99.0))


def test_model_checkpoint():
    """Verify ModelCheckpoint saves only on improvement and preserves optimizer state."""
    model = nn.Linear(4, 2)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt = ModelCheckpoint(
            checkpoint_dir=tmpdir,
            monitor="val_auroc",
            mode="max",
            save_best_only=True,
            filename_prefix="test_model",
        )

        # Epoch 1: save
        p1 = ckpt.step(epoch=1, metric_value=0.80, model=model, optimizer=optimizer)
        assert p1 is not None
        assert p1.exists()

        # Epoch 2: worse score -> no save
        p2 = ckpt.step(epoch=2, metric_value=0.75, model=model, optimizer=optimizer)
        assert p2 is None

        # Epoch 3: better score -> saves best
        p3 = ckpt.step(epoch=3, metric_value=0.85, model=model, optimizer=optimizer)
        assert p3 is not None
        assert p3.exists()

        # Checkpoint load test
        loaded = torch.load(p3, weights_only=False)
        assert loaded["epoch"] == 3
        assert loaded["metric_value"] == 0.85
        assert "optimizer_state_dict" in loaded


def test_mlflow_tracker_local_mode():
    """Verify MLflowTracker functions seamlessly in local/fallback mode."""
    tracker = MLflowTracker(use_mlflow=False)

    with tracker.start_run(run_name="test_run", tags={"environment": "test"}):
        tracker.log_param("learning_rate", 0.001)
        tracker.log_metric("train_loss", 0.45, step=1)
        tracker.log_metric("train_loss", 0.35, step=2)

        history = tracker.get_metric_history("train_loss")
        assert len(history) == 2
        assert history == [0.45, 0.35]
        assert tracker.params["learning_rate"] == 0.001

    assert tracker.active_run_id is None


# ── Vision Trainer Tests ────────────────────────────────────────────────────


def test_chest_xray_trainer_epoch_and_train():
    """Verify ChestXRayTrainer single epoch, multi-epoch loop, and evaluation."""
    torch.manual_seed(42)
    # Synthetic batch of 8 images [3, 32, 32] and 5 labels
    images_tr = torch.randn(12, 3, 32, 32)
    labels_tr = torch.randint(0, 2, (12, 5)).float()
    images_val = torch.randn(6, 3, 32, 32)
    labels_val = torch.randint(0, 2, (6, 5)).float()

    train_loader = DataLoader(TensorDataset(images_tr, labels_tr), batch_size=4)
    val_loader = DataLoader(TensorDataset(images_val, labels_val), batch_size=4)

    model = ChestXRayClassifier(backbone="densenet121", num_classes=5, pretrained=False)
    config = ImageModelConfig(num_epochs=2, batch_size=4, early_stopping_patience=3)

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint = ModelCheckpoint(checkpoint_dir=tmpdir, monitor="val_macro_auroc", mode="max")
        trainer = ChestXRayTrainer(
            model=model,
            config=config,
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=val_loader,
            checkpoint=checkpoint,
        )

        # Single epoch train
        train_res = trainer.train_epoch(epoch=1)
        assert "train_loss" in train_res
        assert train_res["train_loss"] >= 0.0

        # Full short training run
        result = trainer.train(num_epochs=2)
        assert result["epochs_completed"] == 2
        assert len(result["history"]["train_loss"]) == 2

        # Evaluation report
        report = trainer.evaluate(dataloader=val_loader, split_name="val")
        assert report.multilabel_metrics is not None
        assert report.multilabel_metrics.macro_auroc >= 0.0


# ── Tabular Trainer Tests ───────────────────────────────────────────────────


def test_tabular_mlp_trainer():
    """Verify TabularMLPTrainer forward, backward, training loop, and evaluation."""
    torch.manual_seed(42)
    X_tr = torch.randn(20, 13)
    y_tr = torch.randint(0, 2, (20,)).float()
    X_val = torch.randn(10, 13)
    y_val = torch.randint(0, 2, (10,)).float()

    train_loader = DataLoader(TensorDataset(X_tr, y_tr), batch_size=5)
    val_loader = DataLoader(TensorDataset(X_val, y_val), batch_size=5)

    model = TabularRiskMLP(num_features=13, hidden_dims=[32, 16], dropout_rate=0.1)
    config = TabularModelConfig(num_epochs=2, batch_size=5)

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint = ModelCheckpoint(checkpoint_dir=tmpdir, monitor="val_auroc", mode="max")
        trainer = TabularMLPTrainer(
            model=model,
            config=config,
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=val_loader,
            checkpoint=checkpoint,
        )

        res = trainer.train(num_epochs=2)
        assert res["epochs_completed"] == 2
        assert len(res["history"]["val_auroc"]) == 2

        report = trainer.evaluate(dataloader=val_loader, split_name="val")
        assert report.binary_metrics is not None
        assert 0.0 <= report.binary_metrics.auroc <= 1.0


def test_tree_model_trainer():
    """Verify TreeModelTrainer with post-hoc calibration."""
    np.random.seed(42)
    X_tr = np.random.randn(50, 13).astype(np.float32)
    y_tr = np.random.randint(0, 2, size=50).astype(np.float32)
    X_val = np.random.randn(20, 13).astype(np.float32)
    y_val = np.random.randint(0, 2, size=20).astype(np.float32)

    rf_model = RandomForestRiskClassifier(n_estimators=10, max_depth=3)
    trainer = TreeModelTrainer(model=rf_model, calibrate=True, calibration_method="isotonic")

    fit_res = trainer.fit(X_tr, y_tr, X_val=X_val, y_val=y_val)
    assert "train_metrics" in fit_res
    assert "val_metrics" in fit_res

    probs = trainer.predict_proba(X_val)
    assert probs.shape == (20,)
    assert np.all((probs >= 0.0) & (probs <= 1.0))

    report = trainer.evaluate(X_val, y_val, split_name="test")
    assert report.binary_metrics is not None
    assert report.binary_metrics.n_samples == 20


# ── Multimodal Fusion Trainer Tests ─────────────────────────────────────────


class MockMultimodalDataset(Dataset):
    def __init__(self, n_samples=12):
        self.images = torch.randn(n_samples, 3, 32, 32)
        self.tabular = torch.randn(n_samples, 13)
        self.path_labels = torch.randint(0, 2, (n_samples, 5)).float()
        self.risk_labels = torch.randint(0, 2, (n_samples,)).float()
        self.n_samples = n_samples

    def __len__(self):
        return self.n_samples

    def __getitem__(self, idx):
        return {
            "image_tensor": self.images[idx],
            "tabular_tensor": self.tabular[idx],
            "image_labels": self.path_labels[idx],
            "risk_label": self.risk_labels[idx],
        }


def test_multimodal_fusion_trainer_two_stage():
    """Verify MultimodalFusionTrainer two-stage freezing, training, and multi-task evaluation."""
    torch.manual_seed(42)
    train_loader = DataLoader(MockMultimodalDataset(n_samples=8), batch_size=4)
    val_loader = DataLoader(MockMultimodalDataset(n_samples=4), batch_size=4)

    model = MultimodalLateFusionModel(
        image_backbone="densenet121",
        num_image_classes=5,
        num_tabular_features=13,
        fusion_strategy="concat",
        fusion_hidden_dim=32,
        pretrained_vision=False,
    )
    config = FusionModelConfig(
        num_epochs=3,
        fine_tune_after_epoch=1,
        batch_size=4,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint = ModelCheckpoint(checkpoint_dir=tmpdir, monitor="val_combined_score", mode="max")
        trainer = MultimodalFusionTrainer(
            model=model,
            config=config,
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=val_loader,
            checkpoint=checkpoint,
        )

        res = trainer.train(num_epochs=3)
        assert res["epochs_completed"] == 3
        assert len(res["history"]["val_combined_score"]) == 3

        report = trainer.evaluate(dataloader=val_loader, split_name="test")
        assert report.task_type == "multimodal"
        assert report.binary_metrics is not None
        assert report.multilabel_metrics is not None
