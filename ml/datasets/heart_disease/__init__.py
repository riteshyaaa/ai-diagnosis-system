"""
MedFusion AI — Heart Disease Dataset Module.

Handles UCI Heart Disease (and optionally Framingham) datasets:
  - CSV loading and schema validation (pandera)
  - Missing-value imputation strategy
  - Feature engineering (derived clinical features)
  - Categorical encoding and normalization
  - Stratified train / val / test splitting
"""
