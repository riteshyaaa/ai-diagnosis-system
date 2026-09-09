# MedFusion AI — ML Pipeline

## Overview

The machine learning subsystem consists of three core modeling tracks:

1. **Image Model** — Deep convolutional network (DenseNet-121 / EfficientNet-B0) trained on chest X-ray images for multi-label pathology classification.
2. **Tabular Model** — Gradient-boosted decision trees (XGBoost) and linear baselines trained on structured clinical parameters for risk prediction.
3. **Multimodal Fusion Model** — Late-fusion multilayer perceptron combining intermediate embeddings from both modalities with temperature-scaled uncertainty estimation.

## Pipeline Stages

```
1. Data Ingestion & Validation (pandera, PIL)
   ├── Patient-level train/val/test splitting (prevent leakage)
   └── Stratified by primary outcome

2. Preprocessing & Augmentation
   ├── Images: Albumentations (flip, rotate, brightness, contrast, normalize)
   └── Tabular: Median/mode imputation, standard scaling, one-hot encoding

3. Model Training & Tuning
   ├── Image: Transfer learning with frozen backbone → full fine-tuning
   ├── Tabular: 5-fold cross-validation with Optuna hyperparameter optimization
   └── Fusion: Joint training with progressive encoder unfreezing

4. Evaluation & Calibration
   ├── Multi-metric: AUC-ROC, Sensitivity, Specificity, F1, Brier Score
   ├── Probability calibration: Isotonic regression / Platt scaling
   └── Subgroup fairness analysis (age, sex)

5. Explainability Generation
   ├── Grad-CAM saliency heatmaps for chest X-rays
   └── SHAP (TreeExplainer / KernelExplainer) for tabular features

6. Export & Registry
   ├── Model serialization: TorchScript / ONNX / joblib
   └── Versioned metadata in models/registry/
```
