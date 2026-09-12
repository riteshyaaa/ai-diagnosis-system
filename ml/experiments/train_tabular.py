"""
MedFusion AI — Clinical Tabular Risk Model Training Pipeline.

Usage:
    python -m ml.experiments.train_tabular --model-type mlp --epochs 20
    python -m ml.experiments.train_tabular --model-type xgboost
    python -m ml.experiments.train_tabular --model-type random_forest
"""

import argparse
import logging
from pathlib import Path

import torch
from torch.utils.data import DataLoader, TensorDataset

from ml.config import TabularModelConfig
from ml.datasets.synthetic import SyntheticClinicalTabularGenerator
from ml.models.tabular.neural_models import TabularRiskMLP
from ml.models.tabular.tree_models import RandomForestRiskClassifier, XGBoostRiskClassifier
from ml.training.tabular_trainer import TabularMLPTrainer, TreeModelTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_tabular_experiment(
    model_type: str = "mlp",
    epochs: int = 15,
    batch_size: int = 16,
    output_dir: str = "checkpoints/tabular",
) -> None:
    """Run an end-to-end clinical tabular model experiment."""
    logger.info("Initializing tabular experiment: model=%s", model_type)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    gen = SyntheticClinicalTabularGenerator(random_seed=42)
    X_tr, y_tr = gen.generate_array(n_samples=100, normalize=True)
    X_val, y_val = gen.generate_array(n_samples=40, normalize=True)
    X_ts, y_ts = gen.generate_array(n_samples=40, normalize=True)

    if model_type == "mlp":
        config = TabularModelConfig(num_epochs=epochs, batch_size=batch_size, checkpoint_dir=output_dir)

        train_ds = TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr))
        val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))
        test_ds = TensorDataset(torch.from_numpy(X_ts), torch.from_numpy(y_ts))

        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
        test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

        model = TabularRiskMLP(num_features=13, hidden_dims=[64, 32], dropout_rate=0.2)
        trainer = TabularMLPTrainer(
            model=model,
            config=config,
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=test_loader,
        )

        trainer.train(num_epochs=epochs)
        report = trainer.evaluate(dataloader=test_loader, split_name="test")
        report_path = Path(output_dir) / "tabular_mlp_evaluation_report.json"
        report.save(report_path)

    elif model_type in ("xgboost", "random_forest"):
        if model_type == "xgboost":
            model = XGBoostRiskClassifier(n_estimators=50, max_depth=3, learning_rate=0.05)
        else:
            model = RandomForestRiskClassifier(n_estimators=50, max_depth=4)

        trainer = TreeModelTrainer(model=model, calibrate=True, calibration_method="isotonic")
        trainer.fit(X_tr, y_tr, X_val=X_val, y_val=y_val)

        report = trainer.evaluate(X_ts, y_ts, split_name="test")
        report_path = Path(output_dir) / f"{model_type}_evaluation_report.json"
        report.save(report_path)

    logger.info("Tabular experiment finished successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MedFusion AI Tabular Training Experiment")
    parser.add_argument("--model-type", type=str, default="mlp", choices=["mlp", "xgboost", "random_forest"])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    run_tabular_experiment(
        model_type=args.model_type,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
