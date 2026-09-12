"""
MedFusion AI — Multimodal Fusion Model Two-Stage Training Pipeline.

Usage:
    python -m ml.experiments.train_fusion --strategy concat --epochs 10
    python -m ml.experiments.train_fusion --strategy gated --epochs 10
    python -m ml.experiments.train_fusion --strategy attention --epochs 10
"""

import argparse
import logging
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset

from ml.config import FusionModelConfig
from ml.datasets.synthetic import SyntheticMultimodalGenerator
from ml.models.fusion.late_fusion import MultimodalLateFusionModel
from ml.training.fusion_trainer import MultimodalFusionTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class SyntheticMultimodalDataset(Dataset):
    """Wrapper to serve paired image and tabular batches."""

    def __init__(self, n_samples: int = 50, image_size: int = 64, random_seed: int = 42):
        gen = SyntheticMultimodalGenerator(image_size=image_size, num_image_classes=5, random_seed=random_seed)
        self.batch = gen.generate_batch(batch_size=n_samples)
        self.n_samples = n_samples

    def __len__(self) -> int:
        return self.n_samples

    def __getitem__(self, idx: int) -> dict:
        return {
            "image_tensor": self.batch["image_tensor"][idx],
            "tabular_tensor": self.batch["tabular_tensor"][idx],
            "image_labels": self.batch["image_labels"][idx],
            "risk_label": self.batch["risk_label"][idx],
        }


def run_fusion_experiment(
    strategy: str = "concat",
    epochs: int = 6,
    fine_tune_after_epoch: int = 3,
    batch_size: int = 8,
    output_dir: str = "checkpoints/fusion",
) -> None:
    """Run multimodal two-stage fusion training and validation."""
    logger.info("Initializing multimodal fusion experiment: strategy=%s, epochs=%d", strategy, epochs)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    config = FusionModelConfig(
        fusion_strategy=strategy,
        num_epochs=epochs,
        fine_tune_after_epoch=fine_tune_after_epoch,
        batch_size=batch_size,
        checkpoint_dir=output_dir,
    )

    train_ds = SyntheticMultimodalDataset(n_samples=40, random_seed=100)
    val_ds = SyntheticMultimodalDataset(n_samples=16, random_seed=101)
    test_ds = SyntheticMultimodalDataset(n_samples=16, random_seed=102)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    model = MultimodalLateFusionModel(
        image_backbone="densenet121",
        num_image_classes=5,
        num_tabular_features=13,
        fusion_strategy=strategy,
        fusion_hidden_dim=64,
        pretrained_vision=False,
    )

    trainer = MultimodalFusionTrainer(
        model=model,
        config=config,
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
    )

    result = trainer.train(num_epochs=epochs)
    logger.info("Fusion training complete. Best combined score: %.4f", result["best_combined_score"])

    report = trainer.evaluate(dataloader=test_loader, split_name="test")
    report_path = Path(output_dir) / f"fusion_{strategy}_evaluation_report.json"
    report.save(report_path)
    logger.info("Saved final multimodal evaluation report to %s", report_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MedFusion AI Multimodal Training Experiment")
    parser.add_argument("--strategy", type=str, default="concat", choices=["concat", "gated", "attention"])
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--fine-tune-after", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    run_fusion_experiment(
        strategy=args.strategy,
        epochs=args.epochs,
        fine_tune_after_epoch=args.fine_tune_after,
        batch_size=args.batch_size,
    )
