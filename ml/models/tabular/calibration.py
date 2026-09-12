"""
MedFusion AI — Probability Calibration & Uncertainty Quantification.

Provides:
- Isotonic regression and Platt sigmoid calibration for clinical risk assessment
- Expected Calibration Error (ECE) computation
- Brier score and Reliability Diagram curve computation
- Rigorous probabilistic evaluation ensuring model confidence reflects true prevalence
"""

from typing import Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss


def compute_expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """
    Compute Expected Calibration Error (ECE):
    ECE = sum_{m=1}^M (|B_m| / N) * |acc(B_m) - conf(B_m)|
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total_samples = len(y_true)

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        if i == n_bins - 1:
            in_bin = (y_prob >= bin_lower) & (y_prob <= bin_upper)
        else:
            in_bin = (y_prob >= bin_lower) & (y_prob < bin_upper)

        bin_count = np.sum(in_bin)
        if bin_count > 0:
            bin_acc = np.mean(y_true[in_bin])
            bin_conf = np.mean(y_prob[in_bin])
            ece += (bin_count / total_samples) * np.abs(bin_acc - bin_conf)

    return float(ece)


def compute_maximum_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """
    Compute Maximum Calibration Error (MCE):
    MCE = max_{m=1}^M |acc(B_m) - conf(B_m)|
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    mce = 0.0

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        if i == n_bins - 1:
            in_bin = (y_prob >= bin_lower) & (y_prob <= bin_upper)
        else:
            in_bin = (y_prob >= bin_lower) & (y_prob < bin_upper)

        bin_count = np.sum(in_bin)
        if bin_count > 0:
            bin_acc = np.mean(y_true[in_bin])
            bin_conf = np.mean(y_prob[in_bin])
            diff = np.abs(bin_acc - bin_conf)
            if diff > mce:
                mce = float(diff)

    return float(mce)


class ProbabilityCalibrator:
    """
    Post-hoc probability calibration for tabular and multimodal risk predictions.
    Supports non-parametric Isotonic Regression and parametric Platt Scaling (logistic sigmoid).
    """

    def __init__(self, method: str = "isotonic"):
        self.method = method.lower()
        if self.method not in ("isotonic", "platt", "sigmoid"):
            raise ValueError(f"Unsupported calibration method '{method}'. Choose 'isotonic' or 'platt'.")

        self.calibrator = None
        self.is_fitted = False

    def fit(self, uncalibrated_probs: np.ndarray, y_true: np.ndarray) -> "ProbabilityCalibrator":
        """Fit calibration mapping on validation set probabilities."""
        probs = np.asarray(uncalibrated_probs, dtype=np.float64).ravel()
        labels = np.asarray(y_true, dtype=int).ravel()

        if self.method == "isotonic":
            self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            self.calibrator.fit(probs, labels)
        elif self.method in ("platt", "sigmoid"):
            # Platt scaling: LogisticRegression on log-odds or uncalibrated probs
            self.calibrator = LogisticRegression(C=1.0, solver="lbfgs")
            self.calibrator.fit(probs.reshape(-1, 1), labels)

        self.is_fitted = True
        return self

    def calibrate(self, uncalibrated_probs: np.ndarray) -> np.ndarray:
        """Apply calibrated probability transformation."""
        if not self.is_fitted:
            raise RuntimeError("Calibrator has not been fitted. Call fit() first.")

        probs = np.asarray(uncalibrated_probs, dtype=np.float64).ravel()
        if self.method == "isotonic":
            calibrated = self.calibrator.predict(probs)
        elif self.method in ("platt", "sigmoid"):
            calibrated = self.calibrator.predict_proba(probs.reshape(-1, 1))[:, 1]

        # Ensure bounded [0, 1]
        return np.clip(calibrated, 0.0, 1.0)

    def predict_proba(self, uncalibrated_probs: np.ndarray) -> np.ndarray:
        """Alias for calibrate() to match sklearn estimator interface."""
        return self.calibrate(uncalibrated_probs)

    def evaluate_calibration(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        n_bins: int = 10,
    ) -> Dict[str, Union[float, List[float]]]:
        """Compute comprehensive calibration diagnostics."""
        y_true = np.asarray(y_true).astype(int)
        y_prob = np.asarray(y_prob).astype(float)

        ece = compute_expected_calibration_error(y_true, y_prob, n_bins=n_bins)
        mce = compute_maximum_calibration_error(y_true, y_prob, n_bins=n_bins)
        brier = float(brier_score_loss(y_true, y_prob))

        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins)

        return {
            "ece": round(ece, 4),
            "mce": round(mce, 4),
            "brier_score": round(brier, 4),
            "curve_prob_true": [round(float(p), 4) for p in prob_true],
            "curve_prob_pred": [round(float(p), 4) for p in prob_pred],
        }
