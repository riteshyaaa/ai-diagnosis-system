"""
MedFusion AI — Clinical Tabular Risk Model Trainers (Neural MLP & Gradient Boosted Trees).

Provides:
- TabularMLPTrainer: PyTorch training loop for TabularRiskMLP with calibration tracking
- TreeModelTrainer: Fits XGBoost & Random Forest tabular classifiers with post-hoc probability calibration
- Full validation reporting (AUC-ROC, AUC-PR, Brier Score, ECE, Sensitivity, Specificity)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ml.config import TabularModelConfig
from ml.datasets.heart_disease.constants import CORE_FEATURE_NAMES
from ml.evaluation.metrics import (
    BinaryMetrics,
    EvaluationReport,
    compute_binary_metrics,
    compute_expected_calibration_error,
)
from ml.models.tabular.calibration import ProbabilityCalibrator
from ml.models.tabular.neural_models import TabularRiskMLP
from ml.models.tabular.tree_models import RandomForestRiskClassifier, XGBoostRiskClassifier
from ml.training.callbacks import EarlyStopping, LearningRateSchedulerCallback, ModelCheckpoint
from ml.training.tracker import MLflowTracker

logger = logging.getLogger(__name__)


class TabularMLPTrainer:
    """
    PyTorch training coordinator for TabularRiskMLP.
    """

    def __init__(
        self,
        model: TabularRiskMLP,
        config: Optional[TabularModelConfig] = None,
        train_loader: Optional[DataLoader] = None,
        val_loader: Optional[DataLoader] = None,
        test_loader: Optional[DataLoader] = None,
        optimizer: Optional[torch.optim.Optimizer] = None,
        scheduler: Optional[Any] = None,
        device: Optional[Union[str, torch.device]] = None,
        tracker: Optional[MLflowTracker] = None,
        early_stopping: Optional[EarlyStopping] = None,
        checkpoint: Optional[ModelCheckpoint] = None,
    ):
        self.config = config or TabularModelConfig()
        self.device = torch.device(
            device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.model = model.to(self.device)

        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.tracker = tracker or MLflowTracker(use_mlflow=False)

        # Loss function
        self.criterion = nn.BCEWithLogitsLoss()

        # Optimizer: AdamW
        self.optimizer = optimizer or torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        # Scheduler
        if scheduler is not None:
            self.scheduler_cb = LearningRateSchedulerCallback(scheduler, monitor="val_auroc")
        else:
            base_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                self.optimizer, mode="max", factor=0.5, patience=5
            )
            self.scheduler_cb = LearningRateSchedulerCallback(base_scheduler, monitor="val_auroc")

        # Callbacks
        self.early_stopping = early_stopping or EarlyStopping(
            patience=self.config.early_stopping_patience,
            mode="max",
            monitor="val_auroc",
            restore_best_weights=True,
        )
        self.checkpoint = checkpoint or ModelCheckpoint(
            checkpoint_dir="checkpoints/tabular",
            monitor="val_auroc",
            mode="max",
            save_best_only=True,
            filename_prefix="tabular_mlp",
        )

    def train_epoch(self, epoch: int) -> Dict[str, float]:
        """Run a single training epoch over tabular data."""
        self.model.train()
        total_loss = 0.0
        n_batches = 0

        all_probs = []
        all_labels = []

        if self.train_loader is None or len(self.train_loader) == 0:
            return {"train_loss": 0.0}

        for features, labels in self.train_loader:
            features = features.to(self.device)
            labels = labels.to(self.device).view(-1, 1)

            self.optimizer.zero_grad()
            out = self.model(features)
            logits = out["logits"] if isinstance(out, dict) else out
            loss = self.criterion(logits, labels)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            total_loss += loss.item()
            n_batches += 1

            with torch.no_grad():
                probs = (
                    out["probabilities"].cpu().numpy().ravel()
                    if isinstance(out, dict)
                    else torch.sigmoid(logits).cpu().numpy().ravel()
                )
                all_probs.extend(probs.tolist())
                all_labels.extend(labels.cpu().numpy().ravel().tolist())

        avg_loss = total_loss / max(1, n_batches)
        metrics: Dict[str, float] = {"train_loss": round(avg_loss, 4)}

        if all_probs:
            bm = compute_binary_metrics(all_labels, all_probs)
            metrics["train_auroc"] = bm.auroc
            metrics["train_f1"] = bm.f1

        return metrics

    def validate(self, epoch: int = 0) -> Tuple[float, BinaryMetrics]:
        """Evaluate model on validation dataloader."""
        self.model.eval()
        total_loss = 0.0
        n_batches = 0

        all_probs = []
        all_labels = []

        if self.val_loader is None or len(self.val_loader) == 0:
            empty_metrics = compute_binary_metrics([], [])
            return 0.0, empty_metrics

        with torch.no_grad():
            for features, labels in self.val_loader:
                features = features.to(self.device)
                labels = labels.to(self.device).view(-1, 1)

                out = self.model(features)
                logits = out["logits"] if isinstance(out, dict) else out
                loss = self.criterion(logits, labels)

                total_loss += loss.item()
                n_batches += 1

                probs = (
                    out["probabilities"].cpu().numpy().ravel()
                    if isinstance(out, dict)
                    else torch.sigmoid(logits).cpu().numpy().ravel()
                )
                all_probs.extend(probs.tolist())
                all_labels.extend(labels.cpu().numpy().ravel().tolist())

        avg_loss = total_loss / max(1, n_batches)
        val_metrics = compute_binary_metrics(all_labels, all_probs)

        return avg_loss, val_metrics

    def train(self, num_epochs: Optional[int] = None) -> Dict[str, Any]:
        """Execute complete training loop."""
        epochs = num_epochs or self.config.num_epochs
        history: Dict[str, List[float]] = {
            "train_loss": [],
            "val_loss": [],
            "val_auroc": [],
            "val_f1": [],
            "val_ece": [],
            "lr": [],
        }

        self.tracker.start_run(
            run_name=f"tabular_mlp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self.tracker.log_params(
            {
                "model_type": "TabularRiskMLP",
                "num_features": self.model.num_features,
                "hidden_dims": self.config.hidden_dims,
                "learning_rate": self.config.learning_rate,
                "epochs": epochs,
            }
        )

        logger.info("Starting TabularRiskMLP training for %d epochs on %s", epochs, self.device)

        best_val_auroc = 0.0

        for epoch in range(1, epochs + 1):
            train_res = self.train_epoch(epoch)
            val_loss, val_metrics = self.validate(epoch)

            current_lr = self.scheduler_cb.step(metric_value=val_metrics.auroc)

            # Record history
            history["train_loss"].append(train_res.get("train_loss", 0.0))
            history["val_loss"].append(round(val_loss, 4))
            history["val_auroc"].append(val_metrics.auroc)
            history["val_f1"].append(val_metrics.f1)
            history["val_ece"].append(val_metrics.ece)
            history["lr"].append(current_lr)

            # Log to tracker
            self.tracker.log_metrics(
                {
                    "train_loss": train_res.get("train_loss", 0.0),
                    "val_loss": val_loss,
                    "val_auroc": val_metrics.auroc,
                    "val_auprc": val_metrics.auprc,
                    "val_f1": val_metrics.f1,
                    "val_sensitivity": val_metrics.recall,
                    "val_specificity": val_metrics.specificity,
                    "val_brier_score": val_metrics.brier_score,
                    "val_ece": val_metrics.ece,
                    "lr": current_lr,
                },
                step=epoch,
            )

            logger.info(
                "Epoch [%d/%d] | Train Loss: %.4f | Val Loss: %.4f | Val AUROC: %.4f | Val F1: %.4f | Val ECE: %.4f",
                epoch,
                epochs,
                train_res.get("train_loss", 0.0),
                val_loss,
                val_metrics.auroc,
                val_metrics.f1,
                val_metrics.ece,
            )

            # Checkpoint
            saved_path = self.checkpoint.step(
                epoch=epoch,
                metric_value=val_metrics.auroc,
                model=self.model,
                optimizer=self.optimizer,
                metadata={"val_metrics": val_metrics.to_dict()},
            )
            if saved_path:
                self.tracker.log_artifact(saved_path)

            if val_metrics.auroc > best_val_auroc:
                best_val_auroc = val_metrics.auroc

            # Early stopping check
            should_stop = self.early_stopping.step(
                epoch=epoch,
                metric_value=val_metrics.auroc,
                model=self.model,
            )
            if should_stop:
                logger.info("Early stopping triggered. Halting training.")
                break

        self.tracker.end_run(status="FINISHED")

        return {
            "history": history,
            "best_val_auroc": best_val_auroc,
            "epochs_completed": len(history["train_loss"]),
        }

    def evaluate(
        self,
        dataloader: Optional[DataLoader] = None,
        split_name: str = "test",
    ) -> EvaluationReport:
        """Generate evaluation report on dataloader."""
        dl = dataloader or self.test_loader or self.val_loader
        if dl is None:
            raise ValueError("No dataloader provided for evaluation.")

        self.model.eval()
        all_probs = []
        all_labels = []

        with torch.no_grad():
            for features, labels in dl:
                features = features.to(self.device)
                out = self.model(features)
                probs = (
                    out["probabilities"].cpu().numpy().ravel()
                    if isinstance(out, dict)
                    else torch.sigmoid(out).cpu().numpy().ravel()
                )
                all_probs.extend(probs.tolist())
                all_labels.extend(labels.numpy().ravel().tolist())

        metrics = compute_binary_metrics(all_labels, all_probs)
        _, calib_data = compute_expected_calibration_error(
            np.array(all_labels), np.array(all_probs)
        )

        report = EvaluationReport(
            model_name="TabularRiskMLP",
            dataset_split=split_name,
            task_type="binary",
            timestamp=datetime.utcnow().isoformat(),
            binary_metrics=metrics,
            calibration_data=calib_data,
            metadata={"num_features": self.model.num_features},
        )

        return report


class TreeModelTrainer:
    """
    Trainer for gradient-boosted decision trees (XGBoost) and Random Forests.
    Includes post-hoc Platt/Isotonic probability calibration.
    """

    def __init__(
        self,
        model: Union[XGBoostRiskClassifier, RandomForestRiskClassifier],
        calibrate: bool = True,
        calibration_method: str = "isotonic",
        tracker: Optional[MLflowTracker] = None,
    ):
        self.model = model
        self.calibrate = calibrate
        self.calibration_method = calibration_method
        self.tracker = tracker or MLflowTracker(use_mlflow=False)
        self.calibrator = ProbabilityCalibrator(method=calibration_method) if calibrate else None

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Fit tree model and fit post-hoc probability calibrator on validation split."""
        self.tracker.start_run(
            run_name=f"tree_{self.model.__class__.__name__}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self.tracker.log_params(
            {
                "model_type": self.model.__class__.__name__,
                "calibrate": self.calibrate,
                "calibration_method": self.calibration_method if self.calibrate else "none",
                "n_train_samples": len(X_train),
            }
        )

        logger.info("Training %s on %d samples", self.model.__class__.__name__, len(X_train))

        # Fit underlying tree model
        if isinstance(self.model, XGBoostRiskClassifier) and X_val is not None and y_val is not None:
            self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)])
        else:
            self.model.fit(X_train, y_train)

        # Post-hoc calibration on validation data if available, else training data
        if self.calibrate and self.calibrator is not None:
            calib_X = X_val if X_val is not None else X_train
            calib_y = y_val if y_val is not None else y_train
            raw_probs = self.model.predict_proba(calib_X)
            self.calibrator.fit(raw_probs, calib_y)
            logger.info("Fitted %s probability calibrator", self.calibration_method)

        # Log training metrics
        train_probs = self.predict_proba(X_train)
        train_metrics = compute_binary_metrics(y_train, train_probs)
        self.tracker.log_metrics(
            {
                "train_auroc": train_metrics.auroc,
                "train_auprc": train_metrics.auprc,
                "train_f1": train_metrics.f1,
                "train_brier_score": train_metrics.brier_score,
                "train_ece": train_metrics.ece,
            }
        )

        val_metrics = None
        if X_val is not None and y_val is not None:
            val_probs = self.predict_proba(X_val)
            val_metrics = compute_binary_metrics(y_val, val_probs)
            self.tracker.log_metrics(
                {
                    "val_auroc": val_metrics.auroc,
                    "val_auprc": val_metrics.auprc,
                    "val_f1": val_metrics.f1,
                    "val_sensitivity": val_metrics.recall,
                    "val_specificity": val_metrics.specificity,
                    "val_brier_score": val_metrics.brier_score,
                    "val_ece": val_metrics.ece,
                }
            )

        self.tracker.end_run(status="FINISHED")

        return {
            "train_metrics": train_metrics.to_dict(),
            "val_metrics": val_metrics.to_dict() if val_metrics else None,
        }

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict calibrated probabilities."""
        raw_probs = self.model.predict_proba(X)
        if self.calibrate and self.calibrator is not None:
            return self.calibrator.predict_proba(raw_probs)
        return raw_probs

    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        split_name: str = "test",
    ) -> EvaluationReport:
        """Generate evaluation report."""
        probs = self.predict_proba(X_test)
        metrics = compute_binary_metrics(y_test, probs)
        _, calib_data = compute_expected_calibration_error(y_test, probs)

        return EvaluationReport(
            model_name=self.model.__class__.__name__,
            dataset_split=split_name,
            task_type="binary",
            timestamp=datetime.utcnow().isoformat(),
            binary_metrics=metrics,
            calibration_data=calib_data,
            metadata={"calibrated": self.calibrate},
        )
