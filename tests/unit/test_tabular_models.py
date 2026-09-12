"""
MedFusion AI — Unit Tests for Tabular Risk Models & Probability Calibration.

Tests:
- ProbabilityCalibrator (Isotonic & Platt calibration, ECE, MCE, Brier score)
- TabularRiskMLP (residual architecture, 128-dim embedding extractor, checkpoints)
- XGBoostRiskClassifier (training, feature importances, calibration, model saving)
- RandomForestRiskClassifier baseline
- OptunaTabularTuner Bayesian optimization
"""

import numpy as np
import pytest
import torch
from sklearn.datasets import make_classification

from ml.models.tabular import (
    OptunaTabularTuner,
    ProbabilityCalibrator,
    RandomForestRiskClassifier,
    TabularRiskMLP,
    XGBoostRiskClassifier,
    compute_expected_calibration_error,
    compute_maximum_calibration_error,
)


@pytest.fixture
def synthetic_tabular_dataset():
    """Generate synthetic 13-feature clinical dataset (100 samples)."""
    X, y = make_classification(
        n_samples=100,
        n_features=13,
        n_informative=10,
        n_redundant=3,
        random_state=42,
    )
    X = X.astype(np.float32)
    y = y.astype(int)
    # Split train (70) and val (30)
    return X[:70], y[:70], X[70:], y[70:]


def test_probability_calibrator_isotonic_and_metrics():
    """Verify isotonic calibration and ECE calculation."""
    np.random.seed(42)
    y_true = np.array([0, 0, 0, 1, 0, 1, 1, 1, 1, 1])
    raw_probs = np.array([0.1, 0.2, 0.4, 0.35, 0.45, 0.6, 0.7, 0.75, 0.85, 0.9])

    calibrator = ProbabilityCalibrator(method="isotonic")
    calibrator.fit(raw_probs, y_true)
    calibrated = calibrator.calibrate(raw_probs)

    assert len(calibrated) == len(raw_probs)
    assert (calibrated >= 0.0).all() and (calibrated <= 1.0).all()

    # Metrics
    ece = compute_expected_calibration_error(y_true, calibrated, n_bins=5)
    mce = compute_maximum_calibration_error(y_true, calibrated, n_bins=5)
    assert 0.0 <= ece <= 1.0
    assert 0.0 <= mce <= 1.0

    eval_diag = calibrator.evaluate_calibration(y_true, calibrated, n_bins=5)
    assert "ece" in eval_diag
    assert "brier_score" in eval_diag
    assert "curve_prob_true" in eval_diag


def test_probability_calibrator_platt_sigmoid():
    """Verify Platt scaling logistic calibration."""
    y_true = np.array([0, 0, 0, 1, 1, 1])
    raw_probs = np.array([0.2, 0.3, 0.4, 0.6, 0.8, 0.9])

    calibrator = ProbabilityCalibrator(method="platt")
    calibrator.fit(raw_probs, y_true)
    calibrated = calibrator.calibrate(raw_probs)

    assert len(calibrated) == len(raw_probs)
    assert (calibrated >= 0.0).all() and (calibrated <= 1.0).all()


def test_tabular_risk_mlp_architecture_and_embeddings():
    """Verify TabularRiskMLP forward pass, 128-dim embedding extraction, and prediction."""
    model = TabularRiskMLP(input_dim=13, embedding_dim=128, hidden_dim=128)
    dummy_x = torch.randn(4, 13, dtype=torch.float32)

    # Feature embedding extraction (for multimodal fusion)
    embeddings = model.extract_features(dummy_x)
    assert embeddings.shape == (4, 128)
    assert not torch.isnan(embeddings).any()

    # Full forward pass
    out = model(dummy_x, return_embeddings=True)
    assert "logits" in out
    assert "probabilities" in out
    assert "embeddings" in out
    assert out["probabilities"].shape == (4, 1)

    # NumPy predictions
    np_x = np.random.randn(5, 13).astype(np.float32)
    probs = model.predict_proba(np_x)
    assert probs.shape == (5,)
    assert (probs >= 0.0).all() and (probs <= 1.0).all()

    preds = model.predict(np_x, threshold=0.5)
    assert preds.shape == (5,)
    assert set(np.unique(preds)).issubset({0, 1})


def test_tabular_risk_mlp_checkpoint_roundtrip(tmp_path):
    """Verify neural model checkpoint persistence."""
    ckpt_path = tmp_path / "mlp_test.pt"
    model = TabularRiskMLP(input_dim=13, embedding_dim=128)
    dummy_x = torch.randn(2, 13)

    model.eval()
    with torch.no_grad():
        orig_out = model(dummy_x)

    model.save_checkpoint(ckpt_path)
    assert ckpt_path.exists()

    loaded = TabularRiskMLP.load_checkpoint(ckpt_path)
    loaded.eval()
    with torch.no_grad():
        loaded_out = loaded(dummy_x)

    torch.testing.assert_close(orig_out["probabilities"], loaded_out["probabilities"])


def test_xgboost_risk_classifier_fit_and_importance(synthetic_tabular_dataset, tmp_path):
    """Verify XGBoost training, calibration, feature importance, and persistence."""
    X_train, y_train, X_val, y_val = synthetic_tabular_dataset

    clf = XGBoostRiskClassifier(
        n_estimators=30,
        max_depth=3,
        calibration_method="isotonic",
    )
    clf.fit(X_train, y_train, X_val, y_val)

    assert clf.is_fitted is True

    # Predict probabilities
    probs = clf.predict_proba(X_val)
    assert len(probs) == len(X_val)
    assert (probs >= 0.0).all() and (probs <= 1.0).all()

    # Binary predictions
    preds = clf.predict(X_val, threshold=0.5)
    assert len(preds) == len(X_val)

    # Feature importances
    importances = clf.get_feature_importances()
    assert isinstance(importances, dict)
    assert len(importances) == 13
    assert sum(importances.values()) > 0.0

    # Model save and load
    save_path = tmp_path / "xgb_model.joblib"
    clf.save_model(save_path)
    assert save_path.exists()

    loaded_clf = XGBoostRiskClassifier.load_model(save_path)
    loaded_probs = loaded_clf.predict_proba(X_val)
    np.testing.assert_allclose(probs, loaded_probs, atol=1e-5)


def test_random_forest_risk_classifier(synthetic_tabular_dataset):
    """Verify Random Forest baseline classifier."""
    X_train, y_train, X_val, y_val = synthetic_tabular_dataset
    rf = RandomForestRiskClassifier(n_estimators=20, max_depth=4)
    rf.fit(X_train, y_train)

    probs = rf.predict_proba(X_val)
    assert len(probs) == len(X_val)
    assert (probs >= 0.0).all() and (probs <= 1.0).all()

    importances = rf.get_feature_importances()
    assert len(importances) == 13


def test_optuna_tabular_tuner(synthetic_tabular_dataset):
    """Verify Optuna study executes and finds hyperparameter configuration."""
    X_train, y_train, X_val, y_val = synthetic_tabular_dataset
    tune_res = OptunaTabularTuner.tune_xgboost(
        X_train,
        y_train,
        X_val,
        y_val,
        n_trials=3,
    )

    assert "best_params" in tune_res
    assert "best_val_auc" in tune_res
    assert tune_res["n_trials"] == 3
    assert "max_depth" in tune_res["best_params"]
    assert "learning_rate" in tune_res["best_params"]
