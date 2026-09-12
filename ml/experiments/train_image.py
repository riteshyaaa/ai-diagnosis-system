"""
MedFusion AI — Chest X-Ray Vision Model Training Experiment Pipeline.

Usage:
    python -m ml.experiments.train_image --backbone densenet121 --epochs 10 --batch-size 16
"""

import argparse
import logging
from pathlib import Path

import torch
from torch.utils.data import DataLoader, TensorDataset

from ml.config import ImageModelConfig
from ml.datasets.synthetic import SyntheticChestXRayGenerator
from ml.models.image.classifier import ChestXRayClassifier
from ml.training.image_trainer import ChestXRayTrainer
from ml.training.tracker import MLflowTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_image_experiment(
    backbone: str = "densenet121",
    epochs: int = 5,
    batch_size: int = 8,
    image_size: int = 64,
    use_synthetic: bool = True,
    output_dir: str = "checkpoints/image",
) -> None:
    """Run an end-to-end vision training and evaluation run."""
    logger.info("Initializing image training experiment: backbone=%s, epochs=%d", backbone, epochs)

    config = ImageModelConfig(
        backbone=backbone,
        num_epochs=epochs,
        batch_size=batch_size,
        image_size=image_size,
        checkpoint_dir=output_dir,
    )

    # Prepare datasets (Synthetic for fast reproducible training)
    if use_synthetic:
        gen = SyntheticChestXRayGenerator(image_size=image_size, num_classes=5, random_seed=42)
        images_tr, labels_tr = gen.generate_batch(batch_size=32, normalize=True)
        images_val, labels_val = gen.generate_batch(batch_size=16, normalize=True)
        images_ts, labels_ts = gen.generate_batch(batch_size=16, normalize=True)

        train_ds = TensorDataset(images_tr, labels_tr)
        val_ds = TensorDataset(images_val, labels_val)
        test_ds = TensorDataset(images_ts, labels_ts)

        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
        test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)
    else:
        raise NotImplementedError("Real dataset loading configured via NIH ChestX-ray14 path.")

    # Initialize model
    model = ChestXRayClassifier(
        backbone=backbone,
        num_classes=5,
        pretrained=False,
    )

    # Initialize trainer
    trainer = ChestXRayTrainer(
        model=model,
        config=config,
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
    )

    # Train
    result = trainer.train(num_epochs=epochs)
    logger.info("Training complete. Best validation AUROC: %.4f", result["best_val_auroc"])

    # Evaluate
    report = trainer.evaluate(dataloader=test_loader, split_name="test")
    report_path = Path(output_dir) / f"{backbone}_evaluation_report.json"
    report.save(report_path)
    logger.info("Saved final evaluation report to %s", report_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MedFusion AI Chest X-Ray Training Experiment")
    parser.add_argument("--backbone", type=str, default="densenet121", choices=["densenet121", "efficientnet_b0", "resnet50"])
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--image-size", type=int, default=64)
    args = parser.parse_args()

    run_image_experiment(
        backbone=args.backbone,
        epochs=args.epochs,
        batch_size=args.batch_size,
        image_size=args.image_size,
    )
