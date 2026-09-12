"""
MedFusion AI — Gradient Boosted & Decision Tree Clinical Risk Classifiers.

Provides:
- XGBoostRiskClassifier with automated probability calibration & feature importance attribution
- RandomForestRiskClassifier baseline
- Optuna-powered Bayesian hyperparameter tuning engine
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import joblib
import numpy as np
import optuna
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
import xgboost as xgb

from ml.datasets.heart_disease.constants import CORE_FEATURE_NAMES
from ml.models.tabular.calibration import ProbabilityCalibrator


class XGBoostRiskClassifier:
    """
    XGBoost Classifier tailored for clinical tabular disease risk assessment.
    Features automated probability calibration and feature importance extraction.
    """

    def __init__(
        self,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        n_estimators: int = 150,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        reg_alpha: float = 0.1,
        reg_lambda: float = 1.0,
        scale_pos_weight: float = 1.0,
        random_state: int = 42,
        calibration_method: Optional[str] = "isotonic",
        feature_names: Optional[List[str]] = None,
    ):
        self.params = {
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "n_estimators": n_estimators,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "scale_pos_weight": scale_pos_weight,
            "random_state": random_state,
            "eval_metric": "logloss",
            "enable_categorical": False,
        }
        self.feature_names = feature_names or CORE_FEATURE_NAMES
        self.model = xgb.XGBClassifier(**self.params)
        self.calibration_method = calibration_method
        self.calibrator = (
            ProbabilityCalibrator(method=calibration_method)
            if calibration_method
            else None
        )
        self.is_fitted = False

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> "XGBoostRiskClassifier":
        """
        Train XGBoost risk model and fit post-hoc probability calibrator on validation split.
        """
        eval_set = [(X_train, y_train)]
        if X_val is not None and y_val is not None:
            eval_set.append((X_val, y_val))

        self.model.fit(
            X_train,
            y_train,
            eval_set=eval_set,
            verbose=False,
        )
        self.is_fitted = True

        # Fit probability calibrator on holdout validation data (or training data if val not provided)
        if self.calibrator:
            cal_X = X_val if X_val is not None else X_train
            cal_y = y_val if y_val is not None else y_train
            raw_probs = self.model.predict_proba(cal_X)[:, 1]
            self.calibrator.fit(raw_probs, cal_y)

        return self

    def predict_proba(self, X: np.ndarray, calibrate: bool = True) -> np.ndarray:
        """Predict calibrated disease risk probabilities [0, 1]."""
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted. Call fit() before predict.")

        raw_probs = self.model.predict_proba(X)[:, 1]
        if calibrate and self.calibrator and self.calibrator.is_fitted:
            return self.calibrator.calibrate(raw_probs)
        return raw_probs

    def predict(
        self,
        X: np.ndarray,
        threshold: float = 0.5,
        calibrate: bool = True,
    ) -> np.ndarray:
        """Predict binary diagnostic class (0: Normal / 1: Disease Risk)."""
        probs = self.predict_proba(X, calibrate=calibrate)
        return (probs >= threshold).astype(int)

    def get_feature_importances(self) -> Dict[str, float]:
        """Return normalized feature importances mapped to clinical parameter names."""
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        importances = self.model.feature_importances_
        res = {}
        for idx, imp in enumerate(importances):
            name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
            res[name] = round(float(imp), 4)

        # Sort descending by importance
        return dict(sorted(res.items(), key=lambda item: item[1], reverse=True))

    def save_model(self, path: Union[str, Path]) -> None:
        """Serialize trained model and calibrator to disk."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "calibrator": self.calibrator,
                "feature_names": self.feature_names,
                "params": self.params,
                "is_fitted": self.is_fitted,
            },
            dest,
        )

    @classmethod
    def load_model(cls, path: Union[str, Path]) -> "XGBoostRiskClassifier":
        """Load serialized model from disk."""
        data = joblib.load(path)
        instance = cls(
            feature_names=data.get("feature_names"),
            calibration_method=None,
        )
        instance.model = data["model"]
        instance.calibrator = data.get("calibrator")
        instance.params = data.get("params", {})
        instance.is_fitted = data.get("is_fitted", True)
        return instance


class RandomForestRiskClassifier:
    """Random Forest Baseline Classifier for clinical tabular datasets."""

    def __init__(
        self,
        n_estimators: int = 150,
        max_depth: int = 6,
        min_samples_split: int = 4,
        random_state: int = 42,
        feature_names: Optional[List[str]] = None,
    ):
        self.feature_names = feature_names or CORE_FEATURE_NAMES
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=random_state,
        )
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RandomForestRiskClassifier":
        self.model.fit(X, y)
        self.is_fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")
        return self.model.predict_proba(X)[:, 1]

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        probs = self.predict_proba(X)
        return (probs >= threshold).astype(int)

    def get_feature_importances(self) -> Dict[str, float]:
        importances = self.model.feature_importances_
        res = {}
        for idx, imp in enumerate(importances):
            name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
            res[name] = round(float(imp), 4)
        return dict(sorted(res.items(), key=lambda item: item[1], reverse=True))


class OptunaTabularTuner:
    """Bayesian Hyperparameter Optimization for Tabular Classifiers using Optuna."""

    @staticmethod
    def tune_xgboost(
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        n_trials: int = 25,
        random_seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Run Optuna study to find optimal XGBoost hyperparameters maximizing validation ROC-AUC.
        """
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial: optuna.Trial) -> float:
            params = {
                "max_depth": trial.suggest_int("max_depth", 2, 8),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "n_estimators": trial.suggest_int("n_estimators", 50, 300, step=25),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
                "random_state": random_seed,
                "eval_metric": "logloss",
            }
            clf = xgb.XGBClassifier(**params)
            clf.fit(X_train, y_train, verbose=False)
            probs = clf.predict_proba(X_val)[:, 1]
            return float(roc_auc_score(y_val, probs))

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=n_trials)

        return {
            "best_params": study.best_params,
            "best_val_auc": round(float(study.best_value), 4),
            "n_trials": len(study.trials),
        }
