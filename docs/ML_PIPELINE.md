# MedFusion AI — ML Pipeline

> **Status:** This is an experimental codebase, not a trained clinical pipeline. The repository contains no verified checkpoints, real dataset payloads, calibration artifact, reproducible evaluation report, or clinical validation. Prediction endpoints remain unavailable until a verified compatible model is explicitly promoted.

## Overview

The machine learning subsystem consists of three core modeling tracks:

1. **Image Model** — Deep convolutional network (DenseNet-121 / EfficientNet-B0) trained on chest X-ray images for multi-label pathology classification.
2. **Tabular Model** — Gradient-boosted decision trees (XGBoost) and linear baselines trained on structured clinical parameters for risk prediction.
3. **Multimodal Fusion Model** — Late-fusion multilayer perceptron combining intermediate embeddings from both modalities with temperature-scaled uncertainty estimation.

## Code paths and evidence limits

The stages below describe code that exists or intended workflow. They must not be read as a claim that a real clinical dataset was downloaded, the model was trained, or metrics were independently reproduced. The experiment scripts include synthetic-data paths for software experiments only.

## Pipeline Stages

```
1. Data ingestion & validation (loaders and validators exist)
   └── Dataset acquisition, license/provenance, and split evidence are not checked in

2. Preprocessing & Augmentation
   ├── Images: Albumentations (flip, rotate, brightness, contrast, normalize)
   └── Tabular: Median/mode imputation, standard scaling, one-hot encoding

3. Model training & tuning
   ├── Trainers and experiment scripts exist
   └── Some experiment paths use synthetic data; no trained checkpoint is included

4. Evaluation & calibration
   ├── Metric and calibration code exists
   └── No attributable evaluation report or calibration artifact was found

5. Explainability Generation
   ├── Grad-CAM saliency heatmaps for chest X-rays
   └── SHAP (TreeExplainer / KernelExplainer) for tabular features

6. Export & registry
   ├── Registry serialization and checksum checks exist
   └── Active model promotion requires an existing checksum-valid artifact
```
