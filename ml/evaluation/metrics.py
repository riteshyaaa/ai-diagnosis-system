"""
MedFusion AI — Clinical Machine Learning Evaluation & Validation Metrics Engine.

Provides comprehensive, clinically rigorous evaluation metrics for:
- Multi-label thoracic pathology classification (AUC-ROC, AUC-PR, Sensitivity, Specificity, F1)
- Binary cardiovascular risk classification (AUC-ROC, AUC-PR, Brier Score, ECE)
- Expected Calibration Error (ECE) with reliability diagram computation
- Demographic & subgroup fairness evaluation
- Structured, serializable evaluation reports for MLflow logging and clinical auditing
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


@dataclass
class BinaryMetrics:
    """Standard clinical metrics for a single binary classification task."""

    auroc: float
    auprc: float
    accuracy: float
    precision: float
    recall: float  # Sensitivity
    specificity: float
    f1: float
    brier_score: float
    ece: float
    threshold: float
    tp: int
    fp: int
    tn: int
    fn: int
    n_samples: int
    n_positives: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MultiLabelMetrics:
    """Metrics for multi-label clinical diagnosis across N pathologies."""

    macro_auroc: float
    micro_auroc: float
    macro_auprc: float
    macro_f1: float
    macro_sensitivity: float
    macro_specificity: float
    per_class_metrics: Dict[str, BinaryMetrics]
    class_names: List[str]
    n_samples: int

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["per_class_metrics"] = {
            cls_name: metrics.to_dict() if isinstance(metrics, BinaryMetrics) else metrics
            for cls_name, metrics in self.per_class_metrics.items()
        }
        return result


@dataclass
class EvaluationReport:
    """
    Comprehensive, auditable model validation report.
    Serializes to JSON for regulatory and clinical compliance tracking.
    """

    model_name: str
    dataset_split: str
    task_type: str  # "binary", "multi_label", or "multimodal"
    timestamp: str
    binary_metrics: Optional[BinaryMetrics] = None
    multilabel_metrics: Optional[MultiLabelMetrics] = None
    calibration_data: Optional[Dict[str, List[float]]] = None
    subgroup_metrics: Optional[Dict[str, Dict[str, float]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "model_name": self.model_name,
            "dataset_split": self.dataset_split,
            "task_type": self.task_type,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
        if self.binary_metrics:
            data["binary_metrics"] = self.binary_metrics.to_dict()
        if self.multilabel_metrics:
            data["multilabel_metrics"] = self.multilabel_metrics.to_dict()
        if self.calibration_data:
            data["calibration_data"] = self.calibration_data
        if self.subgroup_metrics:
            data["subgroup_metrics"] = self.subgroup_metrics
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, output_path: Union[str, Path]) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        logger.info("Evaluation report saved to %s", path)
        return path


def compute_expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> Tuple[float, Dict[str, List[float]]]:
    """
    Compute Expected Calibration Error (ECE) and reliability curve data.

    ECE = sum_{m=1}^M (|B_m| / N) * |acc(B_m) - conf(B_m)|

    Args:
        y_true: Binary ground truth labels (0 or 1).
        y_prob: Predicted probabilities in [0, 1].
        n_bins: Number of equal-width probability bins.

    Returns:
        (ece_score, reliability_dict)
    """
    y_true = np.asarray(y_true, dtype=float).ravel()
    y_prob = np.asarray(y_prob, dtype=float).ravel()

    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]

    ece = 0.0
    bin_accuracies = []
    bin_confidences = []
    bin_counts = []

    n = len(y_true)
    if n == 0:
        return 0.0, {"prob_true": [], "prob_pred": [], "bin_counts": []}

    for lower, upper in zip(bin_lowers, bin_uppers):
        in_bin = (y_prob >= lower) & (y_prob < upper)
        prop_in_bin = np.mean(in_bin)

        if np.sum(in_bin) > 0:
            accuracy_in_bin = np.mean(y_true[in_bin])
            avg_confidence_in_bin = np.mean(y_prob[in_bin])
            ece += np.abs(accuracy_in_bin - avg_confidence_in_bin) * prop_in_bin

            bin_accuracies.append(float(accuracy_in_bin))
            bin_confidences.append(float(avg_confidence_in_bin))
            bin_counts.append(int(np.sum(in_bin)))
        else:
            bin_accuracies.append(0.0)
            bin_confidences.append(float((lower + upper) / 2))
            bin_counts.append(0)

    reliability_data = {
        "prob_true": bin_accuracies,
        "prob_pred": bin_confidences,
        "bin_counts": bin_counts,
    }

    return float(ece), reliability_data


def compute_binary_metrics(
    y_true: Union[np.ndarray, List[int]],
    y_prob: Union[np.ndarray, List[float]],
    threshold: float = 0.5,
    n_bins: int = 10,
) -> BinaryMetrics:
    """
    Compute comprehensive clinical binary classification metrics.

    Args:
        y_true: 1D array/list of binary ground truth labels {0, 1}.
        y_prob: 1D array/list of continuous risk probabilities [0, 1].
        threshold: Decision threshold for discrete classification.
        n_bins: Number of bins for ECE calculation.

    Returns:
        BinaryMetrics dataclass instance.
    """
    y_true = np.asarray(y_true, dtype=int).ravel()
    y_prob = np.asarray(y_prob, dtype=float).ravel()

    n_samples = len(y_true)
    if n_samples == 0:
        return BinaryMetrics(
            auroc=0.5,
            auprc=0.0,
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            specificity=0.0,
            f1=0.0,
            brier_score=0.0,
            ece=0.0,
            threshold=threshold,
            tp=0,
            fp=0,
            tn=0,
            fn=0,
            n_samples=0,
            n_positives=0,
        )

    y_pred = (y_prob >= threshold).astype(int)
    n_positives = int(np.sum(y_true == 1))

    # AUROC & AUPRC (handle single-class edge cases gracefully)
    if len(np.unique(y_true)) > 1:
        try:
            auroc = float(roc_auc_score(y_true, y_prob))
        except Exception:
            auroc = 0.5
        try:
            auprc = float(average_precision_score(y_true, y_prob))
        except Exception:
            auprc = float(n_positives / n_samples)
    else:
        auroc = 0.5
        auprc = float(n_positives / n_samples) if n_samples > 0 else 0.0

    # Confusion matrix components
    try:
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
    except Exception:
        tn = int(np.sum((y_true == 0) & (y_pred == 0)))
        fp = int(np.sum((y_true == 0) & (y_pred == 1)))
        fn = int(np.sum((y_true == 1) & (y_pred == 0)))
        tp = int(np.sum((y_true == 1) & (y_pred == 1)))

    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))  # Sensitivity
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    # Brier Score: Mean squared probability error
    brier = float(np.mean((y_prob - y_true) ** 2))

    # Expected Calibration Error
    ece, _ = compute_expected_calibration_error(y_true, y_prob, n_bins=n_bins)

    return BinaryMetrics(
        auroc=round(auroc, 4),
        auprc=round(auprc, 4),
        accuracy=round(acc, 4),
        precision=round(prec, 4),
        recall=round(rec, 4),
        specificity=round(spec, 4),
        f1=round(f1, 4),
        brier_score=round(brier, 4),
        ece=round(ece, 4),
        threshold=threshold,
        tp=int(tp),
        fp=int(fp),
        tn=int(tn),
        fn=int(fn),
        n_samples=n_samples,
        n_positives=n_positives,
    )


def compute_multilabel_metrics(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    class_names: Optional[List[str]] = None,
    threshold: float = 0.5,
) -> MultiLabelMetrics:
    """
    Compute multi-label clinical diagnostic performance metrics.

    Args:
        y_true: Multi-label binary ground truth [n_samples, n_classes].
        y_probs: Continuous predicted probabilities [n_samples, n_classes].
        class_names: Names for each class column.
        threshold: Classification decision threshold.

    Returns:
        MultiLabelMetrics dataclass instance.
    """
    y_true = np.asarray(y_true)
    y_probs = np.asarray(y_probs)

    if y_true.ndim == 1:
        y_true = y_true[:, np.newaxis]
        y_probs = y_probs[:, np.newaxis]

    n_samples, num_classes = y_true.shape
    if class_names is None:
        class_names = [f"Class_{i}" for i in range(num_classes)]

    per_class_metrics: Dict[str, BinaryMetrics] = {}
    aurocs = []
    auprcs = []
    f1s = []
    sensitivities = []
    specificities = []

    for i, name in enumerate(class_names):
        col_true = y_true[:, i]
        col_prob = y_probs[:, i]

        bm = compute_binary_metrics(col_true, col_prob, threshold=threshold)
        per_class_metrics[name] = bm

        aurocs.append(bm.auroc)
        auprcs.append(bm.auprc)
        f1s.append(bm.f1)
        sensitivities.append(bm.recall)
        specificities.append(bm.specificity)

    # Micro AUROC across all flattened labels
    try:
        if len(np.unique(y_true)) > 1:
            micro_auroc = float(roc_auc_score(y_true.ravel(), y_probs.ravel()))
        else:
            micro_auroc = 0.5
    except Exception:
        micro_auroc = 0.5

    macro_auroc = float(np.mean(aurocs)) if aurocs else 0.5
    macro_auprc = float(np.mean(auprcs)) if auprcs else 0.0
    macro_f1 = float(np.mean(f1s)) if f1s else 0.0
    macro_sens = float(np.mean(sensitivities)) if sensitivities else 0.0
    macro_spec = float(np.mean(specificities)) if specificities else 0.0

    return MultiLabelMetrics(
        macro_auroc=round(macro_auroc, 4),
        micro_auroc=round(micro_auroc, 4),
        macro_auprc=round(macro_auprc, 4),
        macro_f1=round(macro_f1, 4),
        macro_sensitivity=round(macro_sens, 4),
        macro_specificity=round(macro_spec, 4),
        per_class_metrics=per_class_metrics,
        class_names=class_names,
        n_samples=n_samples,
    )
