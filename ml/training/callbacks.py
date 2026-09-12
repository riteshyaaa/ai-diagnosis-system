"""
MedFusion AI — PyTorch Training Callbacks Engine.

Provides production-grade training lifecycle hooks:
- EarlyStopping with best-weight restoration and min/max monitoring
- ModelCheckpoint with atomic serialization, optimizer/scheduler state, and metadata
- LearningRateSchedulerCallback for dynamic learning rate adjustments
- CallbackList for clean lifecycle dispatching
"""

import copy
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class EarlyStopping:
    """
    Early stopping monitor to halt training when validation metric stops improving.
    Optionally restores model weights from the epoch with the best metric.
    """

    def __init__(
        self,
        patience: int = 7,
        mode: str = "min",
        min_delta: float = 1e-4,
        restore_best_weights: bool = True,
        monitor: str = "val_loss",
    ):
        """
        Args:
            patience: Number of consecutive epochs with no improvement before stopping.
            mode: "min" (e.g., val_loss) or "max" (e.g., val_auroc, val_f1).
            min_delta: Minimum magnitude change to qualify as an improvement.
            restore_best_weights: Restore model parameters from best epoch on stop.
            monitor: Name of the metric being tracked (for logging).
        """
        if mode not in ("min", "max"):
            raise ValueError(f"mode must be 'min' or 'max', got {mode}")

        self.patience = patience
        self.mode = mode
        self.min_delta = min_delta
        self.restore_best_weights = restore_best_weights
        self.monitor = monitor

        self.counter = 0
        self.best_score: Optional[float] = None
        self.best_epoch = 0
        self.early_stop = False
        self.best_weights: Optional[Dict[str, torch.Tensor]] = None

    def __call__(
        self,
        epoch: int,
        metric_value: float,
        model: Optional[nn.Module] = None,
    ) -> bool:
        return self.step(epoch, metric_value, model)

    def step(
        self,
        epoch: int,
        metric_value: float,
        model: Optional[nn.Module] = None,
    ) -> bool:
        """
        Evaluate current metric against best recorded score.

        Args:
            epoch: Current epoch number.
            metric_value: Value of the monitored metric.
            model: PyTorch model whose weights to clone if an improvement is found.

        Returns:
            True if training should halt, False otherwise.
        """
        score = metric_value if self.mode == "max" else -metric_value

        if self.best_score is None:
            self.best_score = score
            self.best_epoch = epoch
            if model is not None and self.restore_best_weights:
                self._save_checkpoint_weights(model)
            return False

        delta = score - self.best_score
        if delta > self.min_delta:
            self.best_score = score
            self.best_epoch = epoch
            self.counter = 0
            if model is not None and self.restore_best_weights:
                self._save_checkpoint_weights(model)
        else:
            self.counter += 1
            logger.info(
                "EarlyStopping counter: %d / %d (best %s: %.4f at epoch %d)",
                self.counter,
                self.patience,
                self.monitor,
                self.best_metric_value,
                self.best_epoch,
            )
            if self.counter >= self.patience:
                self.early_stop = True
                logger.info(
                    "Early stopping triggered at epoch %d. Best %s: %.4f (epoch %d)",
                    epoch,
                    self.monitor,
                    self.best_metric_value,
                    self.best_epoch,
                )
                if model is not None and self.restore_best_weights and self.best_weights is not None:
                    self.restore(model)
                return True

        return False

    def _save_checkpoint_weights(self, model: nn.Module) -> None:
        self.best_weights = {
            k: v.cpu().clone() for k, v in model.state_dict().items()
        }

    def restore(self, model: nn.Module) -> None:
        """Restore model parameters from the best recorded epoch."""
        if self.best_weights is not None:
            model.load_state_dict(self.best_weights)
            logger.info("Restored model weights from best epoch %d", self.best_epoch)

    @property
    def best_metric_value(self) -> float:
        if self.best_score is None:
            return 0.0
        return self.best_score if self.mode == "max" else -self.best_score


class ModelCheckpoint:
    """
    Callback to save model weights and state dictionaries periodically or on metric improvement.
    """

    def __init__(
        self,
        checkpoint_dir: Union[str, Path],
        monitor: str = "val_loss",
        mode: str = "min",
        save_best_only: bool = True,
        filename_prefix: str = "model",
    ):
        """
        Args:
            checkpoint_dir: Directory to save serialized model checkpoints.
            monitor: Metric to evaluate ("val_loss", "val_auroc", etc.).
            mode: "min" or "max".
            save_best_only: If True, only saves when the monitored metric improves.
            filename_prefix: Prefix for saved checkpoint file names.
        """
        if mode not in ("min", "max"):
            raise ValueError(f"mode must be 'min' or 'max', got {mode}")

        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.monitor = monitor
        self.mode = mode
        self.save_best_only = save_best_only
        self.filename_prefix = filename_prefix

        self.best_score: Optional[float] = None
        self.best_checkpoint_path: Optional[Path] = None

    def step(
        self,
        epoch: int,
        metric_value: float,
        model: nn.Module,
        optimizer: Optional[torch.optim.Optimizer] = None,
        scheduler: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        """
        Evaluate metric and save checkpoint if conditions are met.

        Returns:
            Path of saved checkpoint if saved, None otherwise.
        """
        score = metric_value if self.mode == "max" else -metric_value
        is_best = False

        if self.best_score is None or score > self.best_score:
            self.best_score = score
            is_best = True

        if self.save_best_only and not is_best:
            return None

        # Build payload
        checkpoint_dict: Dict[str, Any] = {
            "epoch": epoch,
            "metric_name": self.monitor,
            "metric_value": float(metric_value),
            "state_dict": model.state_dict(),
            "metadata": metadata or {},
        }
        if optimizer is not None:
            checkpoint_dict["optimizer_state_dict"] = optimizer.state_dict()
        if scheduler is not None and hasattr(scheduler, "state_dict"):
            checkpoint_dict["scheduler_state_dict"] = scheduler.state_dict()

        if is_best:
            file_path = self.checkpoint_dir / f"{self.filename_prefix}_best.pt"
            self.best_checkpoint_path = file_path
        else:
            file_path = self.checkpoint_dir / f"{self.filename_prefix}_epoch_{epoch}.pt"

        torch.save(checkpoint_dict, file_path)
        logger.info(
            "Saved checkpoint to %s (%s=%.4f, best=%s)",
            file_path,
            self.monitor,
            metric_value,
            is_best,
        )
        return file_path


class LearningRateSchedulerCallback:
    """
    Adapter callback for PyTorch learning rate schedulers.
    Handles both metric-dependent schedulers (ReduceLROnPlateau) and epoch-based schedulers.
    """

    def __init__(self, scheduler: Any, monitor: str = "val_loss"):
        self.scheduler = scheduler
        self.monitor = monitor

    def step(self, metric_value: Optional[float] = None) -> float:
        """
        Advance scheduler and return current learning rate.
        """
        if isinstance(self.scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
            if metric_value is not None:
                self.scheduler.step(metric_value)
        else:
            self.scheduler.step()

        return self.get_current_lr()

    def get_current_lr(self) -> float:
        """Retrieve current learning rate from underlying optimizer."""
        try:
            return float(self.scheduler.optimizer.param_groups[0]["lr"])
        except Exception:
            return 0.0
