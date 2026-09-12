"""
MedFusion AI — Chest X-Ray Multi-Label Vision Model Trainer.

Implements a robust clinical PyTorch training loop for ChestXRayClassifier:
- Multi-label BCE loss with positive class frequency rebalancing
- Gradient clipping & AdamW optimization with weight decay
- Learning rate warmup & dynamic scheduling (ReduceLROnPlateau / CosineAnnealing)
- Multi-label validation metrics computation (AUC-ROC, AUC-PR, Sensitivity, Specificity)
- Checkpoint serialization and MLflow experiment tracking
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ml.config import ImageModelConfig
from ml.evaluation.metrics import (
    EvaluationReport,
    MultiLabelMetrics,
    compute_multilabel_metrics,
)
from ml.models.image.classifier import ChestXRayClassifier
from ml.training.callbacks import EarlyStopping, LearningRateSchedulerCallback, ModelCheckpoint
from ml.training.tracker import MLflowTracker

logger = logging.getLogger(__name__)


class ChestXRayTrainer:
    """
    Production-grade training coordinator for multi-label chest radiograph classification.
    """

    def __init__(
        self,
        model: ChestXRayClassifier,
        config: Optional[ImageModelConfig] = None,
        train_loader: Optional[DataLoader] = None,
        val_loader: Optional[DataLoader] = None,
        test_loader: Optional[DataLoader] = None,
        optimizer: Optional[torch.optim.Optimizer] = None,
        scheduler: Optional[Any] = None,
        pos_weight: Optional[torch.Tensor] = None,
        device: Optional[Union[str, torch.device]] = None,
        tracker: Optional[MLflowTracker] = None,
        early_stopping: Optional[EarlyStopping] = None,
        checkpoint: Optional[ModelCheckpoint] = None,
    ):
        self.config = config or ImageModelConfig()
        self.device = torch.device(
            device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.model = model.to(self.device)

        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.tracker = tracker or MLflowTracker(use_mlflow=False)

        # Setup Loss: BCEWithLogitsLoss with positive weighting for class imbalance
        if pos_weight is not None:
            pos_weight = pos_weight.to(self.device)
        self.criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

        # Optimizer: AdamW with weight decay
        self.optimizer = optimizer or torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        # Scheduler
        if scheduler is not None:
            self.scheduler_cb = LearningRateSchedulerCallback(scheduler, monitor="val_macro_auroc")
        else:
            base_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                self.optimizer, mode="max", factor=0.5, patience=3
            )
            self.scheduler_cb = LearningRateSchedulerCallback(
                base_scheduler, monitor="val_macro_auroc"
            )

        # Callbacks
        self.early_stopping = early_stopping or EarlyStopping(
            patience=self.config.early_stopping_patience,
            mode="max",
            monitor="val_macro_auroc",
            restore_best_weights=True,
        )
        self.checkpoint = checkpoint or ModelCheckpoint(
            checkpoint_dir="checkpoints/image",
            monitor="val_macro_auroc",
            mode="max",
            save_best_only=True,
            filename_prefix="chexnet",
        )

    def train_epoch(self, epoch: int) -> Dict[str, float]:
        """Run a single training epoch."""
        self.model.train()
        total_loss = 0.0
        n_batches = 0

        all_preds = []
        all_targets = []

        if self.train_loader is None or len(self.train_loader) == 0:
            return {"train_loss": 0.0}

        for batch_idx, (images, targets) in enumerate(self.train_loader):
            images = images.to(self.device)
            targets = targets.to(self.device)

            self.optimizer.zero_grad()
            out = self.model(images)
            logits = out["logits"] if isinstance(out, dict) else out
            loss = self.criterion(logits, targets)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            total_loss += loss.item()
            n_batches += 1

            with torch.no_grad():
                probs = (
                    out["probabilities"].cpu().numpy()
                    if isinstance(out, dict)
                    else torch.sigmoid(logits).cpu().numpy()
                )
                all_preds.append(probs)
                all_targets.append(targets.cpu().numpy())

        avg_loss = total_loss / max(1, n_batches)
        metrics: Dict[str, float] = {"train_loss": round(avg_loss, 4)}

        if all_preds:
            y_probs = np.vstack(all_preds)
            y_true = np.vstack(all_targets)
            ml_metrics = compute_multilabel_metrics(
                y_true, y_probs, class_names=self.model.class_names
            )
            metrics["train_macro_auroc"] = ml_metrics.macro_auroc
            metrics["train_macro_f1"] = ml_metrics.macro_f1

        return metrics

    def validate(self, epoch: int = 0) -> Tuple[float, MultiLabelMetrics]:
        """Evaluate model on validation dataloader."""
        self.model.eval()
        total_loss = 0.0
        n_batches = 0

        all_preds = []
        all_targets = []

        if self.val_loader is None or len(self.val_loader) == 0:
            empty_metrics = compute_multilabel_metrics(
                np.zeros((1, self.model.num_classes)),
                np.zeros((1, self.model.num_classes)),
                class_names=self.model.class_names,
            )
            return 0.0, empty_metrics

        with torch.no_grad():
            for images, targets in self.val_loader:
                images = images.to(self.device)
                targets = targets.to(self.device)

                out = self.model(images)
                logits = out["logits"] if isinstance(out, dict) else out
                loss = self.criterion(logits, targets)

                total_loss += loss.item()
                n_batches += 1

                probs = (
                    out["probabilities"].cpu().numpy()
                    if isinstance(out, dict)
                    else torch.sigmoid(logits).cpu().numpy()
                )
                all_preds.append(probs)
                all_targets.append(targets.cpu().numpy())

        avg_loss = total_loss / max(1, n_batches)
        y_probs = np.vstack(all_preds)
        y_true = np.vstack(all_targets)

        val_metrics = compute_multilabel_metrics(
            y_true, y_probs, class_names=self.model.class_names
        )

        return avg_loss, val_metrics

    def train(self, num_epochs: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute full training loop with early stopping, checkpointing, and tracking.
        """
        epochs = num_epochs or self.config.num_epochs
        history: Dict[str, List[float]] = {
            "train_loss": [],
            "val_loss": [],
            "val_macro_auroc": [],
            "val_macro_f1": [],
            "lr": [],
        }

        self.tracker.start_run(
            run_name=f"chexnet_{self.model.backbone_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self.tracker.log_params(
            {
                "backbone": self.model.backbone_name,
                "learning_rate": self.config.learning_rate,
                "batch_size": self.config.batch_size,
                "num_classes": self.model.num_classes,
                "epochs": epochs,
            }
        )

        logger.info("Starting ChestXRay training for %d epochs on %s", epochs, self.device)

        best_val_auroc = 0.0

        for epoch in range(1, epochs + 1):
            train_res = self.train_epoch(epoch)
            val_loss, val_metrics = self.validate(epoch)

            current_lr = self.scheduler_cb.step(metric_value=val_metrics.macro_auroc)

            # Record history
            history["train_loss"].append(train_res.get("train_loss", 0.0))
            history["val_loss"].append(round(val_loss, 4))
            history["val_macro_auroc"].append(val_metrics.macro_auroc)
            history["val_macro_f1"].append(val_metrics.macro_f1)
            history["lr"].append(current_lr)

            # Log to tracker
            epoch_logs = {
                "train_loss": train_res.get("train_loss", 0.0),
                "val_loss": val_loss,
                "val_macro_auroc": val_metrics.macro_auroc,
                "val_micro_auroc": val_metrics.micro_auroc,
                "val_macro_f1": val_metrics.macro_f1,
                "val_macro_sensitivity": val_metrics.macro_sensitivity,
                "val_macro_specificity": val_metrics.macro_specificity,
                "lr": current_lr,
            }
            self.tracker.log_metrics(epoch_logs, step=epoch)

            logger.info(
                "Epoch [%d/%d] | Train Loss: %.4f | Val Loss: %.4f | Val Macro AUROC: %.4f | Val Macro F1: %.4f | LR: %.6f",
                epoch,
                epochs,
                train_res.get("train_loss", 0.0),
                val_loss,
                val_metrics.macro_auroc,
                val_metrics.macro_f1,
                current_lr,
            )

            # Checkpoint
            saved_path = self.checkpoint.step(
                epoch=epoch,
                metric_value=val_metrics.macro_auroc,
                model=self.model,
                optimizer=self.optimizer,
                metadata={"val_metrics": val_metrics.to_dict()},
            )
            if saved_path:
                self.tracker.log_artifact(saved_path)

            if val_metrics.macro_auroc > best_val_auroc:
                best_val_auroc = val_metrics.macro_auroc

            # Early stopping check
            should_stop = self.early_stopping.step(
                epoch=epoch,
                metric_value=val_metrics.macro_auroc,
                model=self.model,
            )
            if should_stop:
                logger.info("Early stopping condition satisfied. Halting training.")
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
        """
        Generate formal clinical evaluation report on a given dataloader.
        """
        dl = dataloader or self.test_loader or self.val_loader
        if dl is None:
            raise ValueError("No dataloader provided for evaluation.")

        self.model.eval()
        all_preds = []
        all_targets = []

        with torch.no_grad():
            for images, targets in dl:
                images = images.to(self.device)
                out = self.model(images)
                logits = out["logits"] if isinstance(out, dict) else out
                probs = (
                    out["probabilities"].cpu().numpy()
                    if isinstance(out, dict)
                    else torch.sigmoid(logits).cpu().numpy()
                )
                all_preds.append(probs)
                all_targets.append(targets.cpu().numpy())

        y_probs = np.vstack(all_preds) if all_preds else np.zeros((0, self.model.num_classes))
        y_true = np.vstack(all_targets) if all_targets else np.zeros((0, self.model.num_classes))

        metrics = compute_multilabel_metrics(
            y_true, y_probs, class_names=self.model.class_names
        )

        report = EvaluationReport(
            model_name=f"ChestXRayClassifier_{self.model.backbone_name}",
            dataset_split=split_name,
            task_type="multi_label",
            timestamp=datetime.utcnow().isoformat(),
            multilabel_metrics=metrics,
            metadata={
                "num_classes": self.model.num_classes,
                "backbone": self.model.backbone_name,
            },
        )

        return report
