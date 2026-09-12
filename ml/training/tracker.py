"""
MedFusion AI — MLflow Experiment Tracking Engine with Local Fallback.

Provides unified logging of hyperparameters, per-epoch metrics, model artifacts,
evaluation reports, and reliability curves. Automatically falls back to an in-memory
and local JSON logger if MLflow is not configured or unavailable.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Attempt MLflow import
try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    mlflow = None


class MLflowTracker:
    """
    Production experiment tracker with seamless MLflow integration and local fallback.
    """

    def __init__(
        self,
        experiment_name: str = "medfusion_ai",
        tracking_uri: Optional[str] = None,
        artifact_location: Optional[str] = None,
        use_mlflow: bool = True,
    ):
        """
        Args:
            experiment_name: MLflow experiment name.
            tracking_uri: MLflow tracking server URI or local sqlite/directory path.
            artifact_location: Optional directory for artifact storage.
            use_mlflow: If False, forces local file/in-memory logging.
        """
        self.experiment_name = experiment_name
        self.tracking_uri = tracking_uri
        self.artifact_location = artifact_location
        self.use_mlflow = use_mlflow and MLFLOW_AVAILABLE
        self.active_run_id: Optional[str] = None
        self.active_run_name: Optional[str] = None

        # Local storage for fallback or testing inspection
        self.history: Dict[str, List[Dict[str, Any]]] = {}
        self.params: Dict[str, Any] = {}
        self.tags: Dict[str, str] = {}
        self.artifacts: List[Path] = []

        if self.use_mlflow:
            try:
                if tracking_uri:
                    mlflow.set_tracking_uri(tracking_uri)
                mlflow.set_experiment(experiment_name)
                logger.info("MLflowTracker connected to experiment '%s'", experiment_name)
            except Exception as e:
                logger.warning(
                    "Failed to initialize MLflow (%s). Falling back to local logging.",
                    e,
                )
                self.use_mlflow = False

    def start_run(
        self,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> "MLflowTracker":
        """Start a new tracking run."""
        self.active_run_name = run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.history = {}
        self.params = {}
        self.tags = tags or {}
        self.artifacts = []

        if self.use_mlflow:
            try:
                run = mlflow.start_run(run_name=self.active_run_name, tags=self.tags)
                self.active_run_id = run.info.run_id
                logger.info("Started MLflow run '%s' (ID: %s)", self.active_run_name, self.active_run_id)
            except Exception as e:
                logger.warning("MLflow start_run failed (%s). Continuing in local mode.", e)
                self.active_run_id = f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            self.active_run_id = f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return self

    def end_run(self, status: str = "FINISHED") -> None:
        """End the currently active tracking run."""
        if self.use_mlflow and self.active_run_id is not None:
            try:
                mlflow.end_run(status=status)
                logger.info("Ended MLflow run %s with status %s", self.active_run_id, status)
            except Exception as e:
                logger.warning("MLflow end_run failed: %s", e)
        self.active_run_id = None
        self.active_run_name = None

    def log_param(self, key: str, value: Any) -> None:
        """Log a single hyperparameter."""
        self.params[key] = value
        if self.use_mlflow and self.active_run_id is not None:
            try:
                mlflow.log_param(key, value)
            except Exception as e:
                logger.debug("MLflow log_param failed: %s", e)

    def log_params(self, params: Dict[str, Any]) -> None:
        """Log a dictionary of hyperparameters."""
        for k, v in params.items():
            self.log_param(k, v)

    def log_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
        """Log a scalar metric at a specific epoch/step."""
        if key not in self.history:
            self.history[key] = []
        self.history[key].append({"step": step, "value": float(value)})

        if self.use_mlflow and self.active_run_id is not None:
            try:
                mlflow.log_metric(key, float(value), step=step)
            except Exception as e:
                logger.debug("MLflow log_metric failed: %s", e)

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        """Log multiple scalar metrics at a specific epoch/step."""
        for k, v in metrics.items():
            self.log_metric(k, v, step=step)

    def log_artifact(self, local_path: Union[str, Path], artifact_path: Optional[str] = None) -> None:
        """Log a local file artifact (model checkpoint, confusion matrix, report)."""
        path = Path(local_path)
        if not path.exists():
            logger.warning("Artifact path %s does not exist; skipping log.", path)
            return

        self.artifacts.append(path)
        if self.use_mlflow and self.active_run_id is not None:
            try:
                mlflow.log_artifact(str(path), artifact_path=artifact_path)
                logger.info("Logged artifact to MLflow: %s", path.name)
            except Exception as e:
                logger.warning("MLflow log_artifact failed: %s", e)

    def log_dict(self, dictionary: Dict[str, Any], filename: str) -> None:
        """Serialize a dictionary to JSON and log as an artifact."""
        if self.use_mlflow and self.active_run_id is not None:
            try:
                mlflow.log_dict(dictionary, filename)
                return
            except Exception as e:
                logger.debug("MLflow log_dict failed: %s", e)

        # Fallback local logging
        out_dir = Path("logs") / "artifacts"
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(dictionary, f, indent=2)
        self.log_artifact(file_path)

    def get_metric_history(self, key: str) -> List[float]:
        """Return list of metric values logged for key."""
        return [entry["value"] for entry in self.history.get(key, [])]

    def __enter__(self) -> "MLflowTracker":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        status = "FAILED" if exc_type is not None else "FINISHED"
        self.end_run(status=status)
