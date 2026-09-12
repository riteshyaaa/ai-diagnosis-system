"""
MedFusion AI — Multimodal Fusion Two-Stage Model Trainer.

Implements two-stage training for multimodal fusion architectures:
- Stage 1: Freeze vision & tabular backbones, train fusion layer and diagnostic heads.
- Stage 2: Unfreeze vision backbone with lower fine-tuning learning rate for joint optimization.
- Multi-task loss balancing (multi-label thoracic pathologies + binary cardiovascular risk)
- Missing-modality dropout augmentation for clinical robustness
- MLflow experiment tracking and comprehensive clinical validation reporting
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ml.config import FusionModelConfig
from ml.evaluation.metrics import (
    BinaryMetrics,
    EvaluationReport,
    MultiLabelMetrics,
    compute_binary_metrics,
    compute_expected_calibration_error,
    compute_multilabel_metrics,
)
from ml.models.fusion.late_fusion import MultimodalLateFusionModel
from ml.training.callbacks import EarlyStopping, LearningRateSchedulerCallback, ModelCheckpoint
from ml.training.tracker import MLflowTracker

logger = logging.getLogger(__name__)


class MultimodalFusionTrainer:
    """
    Two-stage multi-task trainer for multimodal fusion models.
    """

    def __init__(
        self,
        model: MultimodalLateFusionModel,
        config: Optional[FusionModelConfig] = None,
        train_loader: Optional[DataLoader] = None,
        val_loader: Optional[DataLoader] = None,
        test_loader: Optional[DataLoader] = None,
        optimizer: Optional[torch.optim.Optimizer] = None,
        scheduler: Optional[Any] = None,
        pathology_weight: float = 1.0,
        risk_weight: float = 1.0,
        device: Optional[Union[str, torch.device]] = None,
        tracker: Optional[MLflowTracker] = None,
        early_stopping: Optional[EarlyStopping] = None,
        checkpoint: Optional[ModelCheckpoint] = None,
    ):
        self.config = config or FusionModelConfig()
        self.device = torch.device(
            device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.model = model.to(self.device)

        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.tracker = tracker or MLflowTracker(use_mlflow=False)

        self.pathology_weight = pathology_weight
        self.risk_weight = risk_weight

        # Losses
        self.pathology_criterion = nn.BCEWithLogitsLoss()
        self.risk_criterion = nn.BCEWithLogitsLoss()

        # Optimizer
        self.optimizer = optimizer or torch.optim.AdamW(
            filter(lambda p: p.requires_grad, self.model.parameters()),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        # Scheduler
        if scheduler is not None:
            self.scheduler_cb = LearningRateSchedulerCallback(scheduler, monitor="val_combined_score")
        else:
            base_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                self.optimizer, mode="max", factor=0.5, patience=4
            )
            self.scheduler_cb = LearningRateSchedulerCallback(
                base_scheduler, monitor="val_combined_score"
            )

        # Callbacks
        self.early_stopping = early_stopping or EarlyStopping(
            patience=self.config.early_stopping_patience,
            mode="max",
            monitor="val_combined_score",
            restore_best_weights=True,
        )
        self.checkpoint = checkpoint or ModelCheckpoint(
            checkpoint_dir="checkpoints/fusion",
            monitor="val_combined_score",
            mode="max",
            save_best_only=True,
            filename_prefix="multimodal_fusion",
        )

    def _setup_stage(self, epoch: int) -> None:
        """
        Transition between Stage 1 (frozen backbone) and Stage 2 (fine-tuning).
        """
        if epoch == 1:
            logger.info("--- Stage 1: Freezing vision backbone for initial fusion head training ---")
            self.model.freeze_vision_backbone(freeze=True)
            # Recreate optimizer for trainable parameters only
            self.optimizer = torch.optim.AdamW(
                filter(lambda p: p.requires_grad, self.model.parameters()),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
            )
        elif epoch == self.config.fine_tune_after_epoch + 1:
            logger.info("--- Stage 2: Unfreezing vision backbone for joint fine-tuning ---")
            self.model.freeze_vision_backbone(freeze=False)
            # Lower learning rate for fine-tuning
            fine_tune_lr = self.config.learning_rate * 0.1
            self.optimizer = torch.optim.AdamW(
                [
                    {"params": self.model.image_model.parameters(), "lr": fine_tune_lr},
                    {"params": self.model.tabular_model.parameters(), "lr": fine_tune_lr},
                    {"params": self.model.fusion_layer.parameters(), "lr": self.config.learning_rate},
                    {"params": self.model.pathology_head.parameters(), "lr": self.config.learning_rate},
                    {"params": self.model.risk_head.parameters(), "lr": self.config.learning_rate},
                ],
                weight_decay=self.config.weight_decay,
            )

    def train_epoch(self, epoch: int) -> Dict[str, float]:
        """Run single multimodal training epoch."""
        self._setup_stage(epoch)
        self.model.train()

        total_loss = 0.0
        total_path_loss = 0.0
        total_risk_loss = 0.0
        n_batches = 0

        if self.train_loader is None or len(self.train_loader) == 0:
            return {"train_loss": 0.0}

        for batch in self.train_loader:
            image_t = batch["image_tensor"].to(self.device)
            tabular_t = batch["tabular_tensor"].to(self.device)
            path_labels = batch["image_labels"].to(self.device)
            risk_labels = batch["risk_label"].to(self.device).view(-1, 1)

            self.optimizer.zero_grad()
            out = self.model(image_t, tabular_t)

            loss_path = self.pathology_criterion(out["pathology_logits"], path_labels)
            loss_risk = self.risk_criterion(out["risk_logits"], risk_labels)

            loss = self.pathology_weight * loss_path + self.risk_weight * loss_risk

            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            total_loss += loss.item()
            total_path_loss += loss_path.item()
            total_risk_loss += loss_risk.item()
            n_batches += 1

        avg_loss = total_loss / max(1, n_batches)
        return {
            "train_loss": round(avg_loss, 4),
            "train_path_loss": round(total_path_loss / max(1, n_batches), 4),
            "train_risk_loss": round(total_risk_loss / max(1, n_batches), 4),
        }

    def validate(self, epoch: int = 0) -> Tuple[float, MultiLabelMetrics, BinaryMetrics, float]:
        """
        Evaluate multimodal model on validation loader.
        Returns: (avg_val_loss, pathology_metrics, risk_metrics, combined_score)
        """
        self.model.eval()
        total_loss = 0.0
        n_batches = 0

        all_path_probs = []
        all_path_targets = []
        all_risk_probs = []
        all_risk_targets = []

        if self.val_loader is None or len(self.val_loader) == 0:
            empty_ml = compute_multilabel_metrics(np.zeros((1, 5)), np.zeros((1, 5)))
            empty_bm = compute_binary_metrics([], [])
            return 0.0, empty_ml, empty_bm, 0.0

        with torch.no_grad():
            for batch in self.val_loader:
                image_t = batch["image_tensor"].to(self.device)
                tabular_t = batch["tabular_tensor"].to(self.device)
                path_labels = batch["image_labels"].to(self.device)
                risk_labels = batch["risk_label"].to(self.device).view(-1, 1)

                out = self.model(image_t, tabular_t)
                loss_path = self.pathology_criterion(out["pathology_logits"], path_labels)
                loss_risk = self.risk_criterion(out["risk_logits"], risk_labels)
                loss = self.pathology_weight * loss_path + self.risk_weight * loss_risk

                total_loss += loss.item()
                n_batches += 1

                all_path_probs.append(out["pathology_probs"].cpu().numpy())
                all_path_targets.append(path_labels.cpu().numpy())
                all_risk_probs.extend(out["risk_prob"].cpu().numpy().ravel().tolist())
                all_risk_targets.extend(risk_labels.cpu().numpy().ravel().tolist())

        avg_loss = total_loss / max(1, n_batches)
        y_path_probs = np.vstack(all_path_probs)
        y_path_true = np.vstack(all_path_targets)

        path_metrics = compute_multilabel_metrics(
            y_path_true, y_path_probs, class_names=self.model.class_names
        )
        risk_metrics = compute_binary_metrics(all_risk_targets, all_risk_probs)

        # Combined score: 50% pathology macro AUROC + 50% cardiovascular risk AUROC
        combined_score = round(0.5 * path_metrics.macro_auroc + 0.5 * risk_metrics.auroc, 4)

        return avg_loss, path_metrics, risk_metrics, combined_score

    def train(self, num_epochs: Optional[int] = None) -> Dict[str, Any]:
        """Execute complete two-stage training loop."""
        epochs = num_epochs or self.config.num_epochs
        history: Dict[str, List[float]] = {
            "train_loss": [],
            "val_loss": [],
            "val_path_macro_auroc": [],
            "val_risk_auroc": [],
            "val_combined_score": [],
            "lr": [],
        }

        self.tracker.start_run(
            run_name=f"fusion_{self.model.fusion_strategy}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        self.tracker.log_params(
            {
                "fusion_strategy": self.model.fusion_strategy,
                "fusion_hidden_dim": self.config.fusion_hidden_dim,
                "learning_rate": self.config.learning_rate,
                "fine_tune_after_epoch": self.config.fine_tune_after_epoch,
                "epochs": epochs,
            }
        )

        logger.info("Starting MultimodalFusion training for %d epochs on %s", epochs, self.device)
        best_combined = 0.0

        for epoch in range(1, epochs + 1):
            train_res = self.train_epoch(epoch)
            val_loss, path_metrics, risk_metrics, combined_score = self.validate(epoch)

            current_lr = self.scheduler_cb.step(metric_value=combined_score)

            # Record history
            history["train_loss"].append(train_res.get("train_loss", 0.0))
            history["val_loss"].append(round(val_loss, 4))
            history["val_path_macro_auroc"].append(path_metrics.macro_auroc)
            history["val_risk_auroc"].append(risk_metrics.auroc)
            history["val_combined_score"].append(combined_score)
            history["lr"].append(current_lr)

            # Log to tracker
            self.tracker.log_metrics(
                {
                    "train_loss": train_res.get("train_loss", 0.0),
                    "val_loss": val_loss,
                    "val_path_macro_auroc": path_metrics.macro_auroc,
                    "val_path_macro_f1": path_metrics.macro_f1,
                    "val_risk_auroc": risk_metrics.auroc,
                    "val_risk_f1": risk_metrics.f1,
                    "val_risk_ece": risk_metrics.ece,
                    "val_combined_score": combined_score,
                    "lr": current_lr,
                },
                step=epoch,
            )

            logger.info(
                "Epoch [%d/%d] | Train Loss: %.4f | Val Loss: %.4f | Path AUROC: %.4f | Risk AUROC: %.4f | Combined: %.4f",
                epoch,
                epochs,
                train_res.get("train_loss", 0.0),
                val_loss,
                path_metrics.macro_auroc,
                risk_metrics.auroc,
                combined_score,
            )

            # Checkpoint
            saved_path = self.checkpoint.step(
                epoch=epoch,
                metric_value=combined_score,
                model=self.model,
                optimizer=self.optimizer,
                metadata={
                    "path_metrics": path_metrics.to_dict(),
                    "risk_metrics": risk_metrics.to_dict(),
                },
            )
            if saved_path:
                self.tracker.log_artifact(saved_path)

            if combined_score > best_combined:
                best_combined = combined_score

            # Early stopping check
            should_stop = self.early_stopping.step(
                epoch=epoch,
                metric_value=combined_score,
                model=self.model,
            )
            if should_stop:
                logger.info("Early stopping triggered. Halting training.")
                break

        self.tracker.end_run(status="FINISHED")

        return {
            "history": history,
            "best_combined_score": best_combined,
            "epochs_completed": len(history["train_loss"]),
        }

    def evaluate(
        self,
        dataloader: Optional[DataLoader] = None,
        split_name: str = "test",
    ) -> EvaluationReport:
        """Generate full multimodal clinical evaluation report."""
        dl = dataloader or self.test_loader or self.val_loader
        if dl is None:
            raise ValueError("No dataloader provided for evaluation.")

        self.model.eval()
        all_path_probs = []
        all_path_targets = []
        all_risk_probs = []
        all_risk_targets = []

        with torch.no_grad():
            for batch in dl:
                image_t = batch["image_tensor"].to(self.device)
                tabular_t = batch["tabular_tensor"].to(self.device)
                path_labels = batch["image_labels"].to(self.device)
                risk_labels = batch["risk_label"].to(self.device).view(-1, 1)

                out = self.model(image_t, tabular_t)
                all_path_probs.append(out["pathology_probs"].cpu().numpy())
                all_path_targets.append(path_labels.cpu().numpy())
                all_risk_probs.extend(out["risk_prob"].cpu().numpy().ravel().tolist())
                all_risk_targets.extend(risk_labels.cpu().numpy().ravel().tolist())

        y_path_probs = np.vstack(all_path_probs) if all_path_probs else np.zeros((0, 5))
        y_path_true = np.vstack(all_path_targets) if all_path_targets else np.zeros((0, 5))

        path_metrics = compute_multilabel_metrics(
            y_path_true, y_path_probs, class_names=self.model.class_names
        )
        risk_metrics = compute_binary_metrics(all_risk_targets, all_risk_probs)
        _, calib_data = compute_expected_calibration_error(
            np.array(all_risk_targets), np.array(all_risk_probs)
        )

        return EvaluationReport(
            model_name=f"MultimodalFusion_{self.model.fusion_strategy}",
            dataset_split=split_name,
            task_type="multimodal",
            timestamp=datetime.utcnow().isoformat(),
            binary_metrics=risk_metrics,
            multilabel_metrics=path_metrics,
            calibration_data=calib_data,
            metadata={
                "fusion_strategy": self.model.fusion_strategy,
                "pathology_macro_auroc": path_metrics.macro_auroc,
                "risk_auroc": risk_metrics.auroc,
            },
        )
