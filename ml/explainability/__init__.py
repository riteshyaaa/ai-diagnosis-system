"""
MedFusion AI — Explainability Package.

Provides clinical model interpretability:
- Grad-CAM activation maps for chest X-ray vision backbones
- SHAP (TreeExplainer / KernelExplainer) for tabular clinical risk models
"""

from ml.explainability.explain import (
    GradCAMExplainer,
    SHAPExplainerEngine,
    explain_vision_model,
    explain_tabular_model,
)

__all__ = [
    "GradCAMExplainer",
    "SHAPExplainerEngine",
    "explain_vision_model",
    "explain_tabular_model",
]