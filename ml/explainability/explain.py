"""
MedFusion AI — Clinical Explainability Engine.

Provides:
- Grad-CAM / Grad-CAM++ activation mapping for chest X-ray vision backbones
- SHAP TreeExplainer for gradient-boosted clinical risk models (XGBoost)
- SHAP KernelExplainer for deep tabular MLP clinical embeddings
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import torch
import torch.nn.functional as F


class GradCAMExplainer:
    """
    Grad-CAM Explainability Engine for Chest Radiograph Deep CNN Backbones.
    Computes gradient-weighted class activation heatmaps for local model interpretation.
    """

    def __init__(
        self,
        model: Any,
        target_layer: Optional[Any] = None,
        device: Optional[str] = None,
    ):
        self.model = model
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()

        # Target layer for Grad-CAM (last convolutional layer)
        if target_layer is not None:
            self.target_layer = target_layer
        elif hasattr(model, "get_last_conv_layer"):
            self.target_layer = model.get_last_conv_layer()
        else:
            raise ValueError("Model must provide get_last_conv_layer() or target_layer must be specified.")

        # Register forward and backward hooks
        self.gradients: Optional[np.ndarray] = None
        self.activations: Optional[np.ndarray] = None
        self.hooks_registered = False
        self._register_hooks()

    def _register_hooks(self) -> None:
        def forward_hook(module, input, output):
            # Store the activation feature map
            self.activations = output.detach().cpu().numpy()

        def backward_hook(module, grad_input, grad_output):
            # Capture gradient of output w.r.t layer output
            if grad_output[0] is not None:
                self.gradients = grad_output[0].detach().cpu().numpy()
            else:
                self.gradients = None

        # Remove existing hooks first (to allow re-registration safely)
        for hook in getattr(self, "_hooks", []):
            hook.remove()
        self._hooks = []

        # Register hooks on target layer
        f_hook = self.target_layer.register_forward_hook(forward_hook)
        b_hook = self.target_layer.register_backward_hook(backward_hook)
        self._hooks = [f_hook, b_hook]
        self.hooks_registered = True

    def generate_heatmap(
        self,
        image_tensor: torch.Tensor,
        class_idx: Optional[int] = None,
        use_positive_only: bool = True,
    ) -> np.ndarray:
        """
        Generate Grad-CAM activation heatmap for a given input image.

        Args:
            image_tensor: Input radiograph [batch_size, 3, H, W] or [3, H, W]
            class_idx: Target pathology class index. If None, uses max probability class.
            use_positive_only: Only use positive gradients (standard Grad-CAM).
        Returns:
            Heatmap array of same spatial resolution as target feature map, normalized [0, 1].
        """
        if not self.hooks_registered:
            self._register_hooks()

        # Ensure correct input shape
        if image_tensor.dim() == 3:
            image_tensor = image_tensor.unsqueeze(0)

        image_tensor = image_tensor.to(self.device)

        # Zero gradients before backward
        self.model.zero_grad()

        # Forward pass
        output = self.model(image_tensor)
        if isinstance(output, dict):
            # Multi-label: output is {logits, scaled_logits, ...}
            if "logits" in output:
                logits = output["logits"]
            elif "scaled_logits" in output:
                logits = output["scaled_logits"]
            else:
                logits = list(output.values())[0]
        else:
            logits = output

        # Determine class index
        if class_idx is None:
            # For multi-label: choose the class with highest positive logit value
            if logits.dim() > 1 and logits.shape[-1] > 1:
                # Multi-label with multiple outputs
                class_idx = int(torch.argmax(torch.sigmoid(logits[0])).item())
            else:
                class_idx = 0

        # Select the target score
        if logits.dim() == 1 or logits.shape[-1] == 1:
            # Single binary output
            score = logits.squeeze()
        else:
            # Multi-output: select specific class
            score = logits[0, class_idx]

        # Backward pass
        score.backward(retain_graph=True)

        # Validate captured tensors
        if self.gradients is None:
            raise RuntimeError("Grad-CAM backward hook failed: no gradient captured. Ensure target_layer is part of the graph.")
        if self.activations is None:
            raise RuntimeError("Grad-CAM forward hook failed: no activation captured.")

        # Average gradients over spatial dimensions per feature map
        gradients_np = self.gradients  # [batch, channels, H, W]
        activations_np = self.activations  # [batch, channels, H, W]

        # Compute weights per feature map (channel)
        # Weight = average gradient for that feature map over spatial dimensions
        weights = np.mean(gradients_np, axis=(2, 3))  # [batch, channels]
        if use_positive_only:
            weights = np.clip(weights, a_min=0, a_max=None)

        # Weighted combination of feature maps
        batch_idx = 0  # For single image explanation
        feature_maps = activations_np[batch_idx]  # [channels, H, W]
        weights_single = weights[batch_idx]  # [channels]

        # Compute weighted feature maps: multiply each channel by its weight, sum
        weighted_maps = feature_maps * weights_single[:, np.newaxis, np.newaxis]
        cam = np.sum(weighted_maps, axis=0)

        # Apply ReLU (positive contributions only for Grad-CAM standard)
        if use_positive_only:
            cam = np.clip(cam, a_min=0, a_max=None)

        # Normalize to [0, 1]
        cam_min = cam.min()
        cam_max = cam.max()
        if cam_max > cam_min:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = np.zeros_like(cam)

        return cam

    def generate_gradcam_plus_plus(
        self,
        image_tensor: torch.Tensor,
        class_idx: Optional[int] = None,
    ) -> np.ndarray:
        """
        Grad-CAM++: Second-order gradient weighting for finer-grained localization.
        Weights feature maps by average positive second partial derivative.
        """
        if not self.hooks_registered:
            self._register_hooks()
        if image_tensor.dim() == 3:
            image_tensor = image_tensor.unsqueeze(0)
        image_tensor = image_tensor.to(self.device)
        self.model.zero_grad()
        output = self.model(image_tensor)
        if isinstance(output, dict):
            logits = output["logits"] if "logits" in output else (output["scaled_logits"] if "scaled_logits" in output else list(output.values())[0])
        else:
            logits = output
        if class_idx is None:
            class_idx = int(torch.argmax(torch.sigmoid(logits[0])).item()) if logits.dim() > 1 and logits.shape[-1] > 1 else 0
        score = logits.squeeze() if logits.dim() == 1 or logits.shape[-1] == 1 else logits[0, class_idx]
        score.backward(retain_graph=True)
        if self.gradients is None or self.activations is None:
            raise RuntimeError("Grad-CAM++ backward hook failed.")
        gradients_np = self.gradients
        activations_np = self.activations
        # Second-order approximation: weight = mean( (grad / (grad + eps)) * (grad^2) ) / mean(grad^2)
        eps = 1e-8
        grads_sq = np.square(gradients_np) + eps
        # For Grad-CAM++: weight per channel = mean(grad^2) / mean(grad^2 + eps) ~ positive normalized weight
        weights = np.mean(grads_sq, axis=(2, 3))
        weights = np.clip(weights, a_min=eps, a_max=None)
        weights = weights / np.max(weights, axis=1, keepdims=True)
        feature_maps = activations_np[0]
        weights_single = weights[0]
        weighted_maps = feature_maps * weights_single[:, np.newaxis, np.newaxis]
        cam = np.sum(weighted_maps, axis=0)
        cam = np.clip(cam, a_min=0, a_max=None)
        cam_min, cam_max = cam.min(), cam.max()
        return (cam - cam_min) / (cam_max - cam_min) if cam_max > cam_min else np.zeros_like(cam)


class SHAPExplainerEngine:
    """
    SHAP (SHapley Additive exPlanations) Explanation Engine for Clinical Models.

    Supports:
    - TreeExplainer for gradient-boosted clinical risk classifiers (XGBoost)
    - KernelExplainer for deep tabular MLP clinical models
    """

    def __init__(self, model: Any):
        try:
            import shap
        except ImportError:
            raise ImportError("SHAP library not installed. Install with: pip install shap")
        self.model = model
        self.model_type = self._detect_model_type()
        self.explainer = None

    def _detect_model_type(self) -> str:
        class_name = self.model.__class__.__name__
        if "XGBoost" in class_name or "RandomForest" in class_name:
            return "tree"
        elif "MLP" in class_name or "TabularRisk" in class_name:
            return "deep_tabular"
        elif hasattr(self.model, "predict_proba"):
            return "probabilistic_model"
        else:
            return "unknown"

    def build_tree_explainer(
        self,
        background_data: Optional[np.ndarray] = None,
    ) -> Any:
        import shap
        if hasattr(self.model, "model"):
            # XGBoostRiskClassifier and RandomForestRiskClassifier wrap their
            # underlying estimator in the `model` attribute.
            actual_model = self.model.model
        else:
            actual_model = self.model
        explainer = shap.TreeExplainer(actual_model, data=background_data, feature_perturbation="tree_path_dependent")
        return explainer

    def build_kernel_explainer(
        self,
        background_data: np.ndarray,
    ) -> Any:
        import shap
        # KernelExplainer requires callable: input (np.ndarray) -> output (np.ndarray)
        # Wrap the model's predict_proba method
        def predict_fn(X: np.ndarray) -> np.ndarray:
            if hasattr(self.model, "predict_proba"):
                return self.model.predict_proba(X)
            elif hasattr(self.model, "predict"):
                probs = np.array([self.model.predict(x.reshape(1, -1))[0] for x in X])
                return np.vstack([1 - probs, probs]).T
            else:
                # For raw ML modules (e.g., neural networks with .forward)
                import torch
                self.model.eval()
                with torch.no_grad():
                    if isinstance(X, torch.Tensor):
                        X_t = X
                    else:
                        X_t = torch.from_numpy(X.astype(np.float32))
                    out = self.model(X_t)
                    if isinstance(out, dict) and "probabilities" in out:
                        return out["probabilities"].cpu().numpy()
                    else:
                        return out.cpu().numpy()
        explainer = shap.KernelExplainer(predict_fn, background_data)
        return explainer

    def explain(
        self,
        X: np.ndarray,
        background_data: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        n_samples: int = 100,
    ) -> Dict[str, Any]:
        """
        Generate SHAP explanations for clinical model predictions.

        Args:
            X: Input clinical feature array [n_samples, n_features]
            background_data: Background dataset for SHAP. If None, uses first 100 samples.
            feature_names: List of feature names (optional)
            n_samples: Number of SHAP value computations (used for KernelExplainer)
        Returns:
            Dictionary with SHAP values, feature importance attributions, and base/expected values.
        """
        import shap

        # Determine background dataset
        if background_data is None:
            if isinstance(X, np.ndarray) and len(X) >= 10:
                background_data = X[:min(100, len(X))]
            else:
                # Default synthetic background for small/empty sets
                background_data = np.random.randn(100, X.shape[1] if X.ndim > 1 else 1).astype(np.float32)

        if self.model_type == "tree":
            self.explainer = self.build_tree_explainer(background_data=background_data)
            # TreeExplainer returns values of shape [n_samples, n_features] for classification
            if hasattr(self.explainer, "expected_value") and np.isscalar(self.explainer.expected_value):
                # Binary classification
                shap_values = self.explainer.shap_values(X)
                # For binary classifiers, TreeExplainer may return list with [neg, pos] or single array
                if isinstance(shap_values, list):
                    # Multi-output: take positive class (index 1) for risk explanation
                    shap_vals = shap_values[1]  # Positive risk class
                    base_val = self.explainer.expected_value[1] if isinstance(self.explainer.expected_value, (list, np.ndarray)) else self.explainer.expected_value
                else:
                    shap_vals = shap_values
                    base_val = self.explainer.expected_value
            else:
                # Single-output binary / regression
                shap_vals = self.explainer.shap_values(X)
                base_val = self.explainer.expected_value

        elif self.model_type == "deep_tabular":
            self.explainer = self.build_kernel_explainer(background_data=background_data.astype(np.float32))
            # KernelExplainer requires subset selection for performance
            X_sample = X[:min(n_samples, len(X))] if len(X) > n_samples else X
            # Run with fewer samples to keep computation manageable
            shap_values = self.explainer.shap_values(X_sample, nsamples=min(50, n_samples))
            # KernelExplainer returns list of arrays for multi-output; take index 1 (positive class)
            if isinstance(shap_values, list) and len(shap_values) > 1:
                shap_vals = np.array(shap_values[1])
            elif isinstance(shap_values, list):
                shap_vals = np.array(shap_values[0])
            else:
                shap_vals = np.array(shap_values)
            base_val = self.explainer.expected_value
        else:
            raise ValueError(f"Unsupported model type for SHAP: {self.model_type}. Use 'tree' or 'deep_tabular'.")

        # Ensure 2D array for SHAP values
        if shap_vals.ndim == 1 and X.ndim == 2:
            # For single-sample input with multi-feature explanation
            if X.shape[0] == 1:
                shap_vals = shap_vals.reshape(1, -1)

        # Feature importance attribution: mean absolute SHAP value per feature
        if shap_vals.ndim == 2 and shap_vals.shape[0] == X.shape[0]:
            feature_importance = np.abs(shap_vals).mean(axis=0)
        elif shap_vals.ndim == 2:
            feature_importance = np.abs(shap_vals).mean(axis=0)
        else:
            # Fallback for unexpected shapes
            feature_importance = np.abs(np.array(shap_vals)).mean(axis=0) if np.array(shap_vals).ndim > 1 else np.abs(np.array(shap_vals))

        feature_importance_dict = {}
        feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1] if X.ndim > 1 else 1)]
        for idx, name in enumerate(feature_names):
            if idx < len(feature_importance):
                feature_importance_dict[name] = round(float(feature_importance[idx]), 4)

        # Sort descending
        feature_importance_dict = dict(sorted(
            feature_importance_dict.items(),
            key=lambda item: item[1],
            reverse=True,
        ))

        # Compute top-K feature contributions for summary reporting
        top_k = min(5, len(feature_importance_dict))
        top_features = list(feature_importance_dict.items())[:top_k]

        return {
            "shap_values": np.array(shap_vals).tolist() if isinstance(shap_vals, np.ndarray) else shap_vals,
            "feature_importance": feature_importance_dict,
            "top_5_features": top_features,
            "base_value": float(base_val) if np.isscalar(base_val) else float(np.array(base_val).mean()),
            "model_type": self.model_type,
            "explanation_method": "TreeExplainer" if self.model_type == "tree" else "KernelExplainer",
        }


def explain_vision_model(
    image_tensor: torch.Tensor,
    model: Any,
    class_idx: Optional[int] = None,
) -> Dict[str, Any]:
    """
    High-level interface: Generate Grad-CAM explanation for vision model.
    Returns dictionary with heatmap array, class info, and explanation metadata.
    """
    explainer = GradCAMExplainer(model=model)
    heatmap = explainer.generate_heatmap(image_tensor, class_idx=class_idx, use_positive_only=True)

    return {
        "heatmap": heatmap.tolist(),
        "heatmap_shape": heatmap.shape if isinstance(heatmap, np.ndarray) else None,
        "explanation_type": "Grad-CAM",
        "target_class_index": class_idx,
        "device_used": explainer.device,
    }


def explain_tabular_model(
    model: Any,
    X: np.ndarray,
    feature_names: Optional[List[str]] = None,
    background_data: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    High-level interface: Generate SHAP explanation for clinical tabular risk model.
    """
    explainer_engine = SHAPExplainerEngine(model=model)
    result = explainer_engine.explain(
        X=X,
        background_data=background_data,
        feature_names=feature_names,
        n_samples=min(50, X.shape[0] if X.ndim > 1 else 1),
    )
    return result
