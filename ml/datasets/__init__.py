"""
MedFusion AI — Datasets Package.

Subpackages:
  - chest_xray/    NIH ChestX-ray14 loading, splitting, augmentation
  - heart_disease/ UCI Heart Disease + Framingham preprocessing

Synthetic data generation:
  - synthetic      SyntheticChestXRayGenerator, SyntheticClinicalTabularGenerator, SyntheticMultimodalGenerator
"""

from ml.datasets.synthetic import (
    SyntheticChestXRayGenerator,
    SyntheticClinicalTabularGenerator,
    SyntheticMultimodalGenerator,
)

__all__ = [
    "SyntheticChestXRayGenerator",
    "SyntheticClinicalTabularGenerator",
    "SyntheticMultimodalGenerator",
]
