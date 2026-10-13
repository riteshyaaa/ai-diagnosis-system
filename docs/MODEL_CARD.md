# Model card and availability

## Intended use

This repository is an educational/research software prototype. It is not a clinically validated diagnostic device and must not be used to diagnose, triage, or guide treatment. It has no verified model checkpoint available for inference.

## Tasks represented in code

The codebase contains architectures and pipeline code for:

- Multi-label chest-radiograph classification.
- Tabular cardiovascular-risk experimentation based on a 13-feature schema.
- Late fusion of image and tabular representations.

Those are code-level task descriptions, not evidence of a trained, calibrated, or clinically useful model.

## Availability and provenance

| Model family | Checkpoint in repository | Evaluation evidence | Deployment state |
|---|---:|---|---|
| Chest radiograph classifier | No | No attributable test set or evaluation report found | Disabled |
| Tabular risk model | No | No attributable test set or calibration artifact found | Disabled |
| Multimodal fusion model | No | No paired evaluation set or report found | Disabled |

The registry manifest is intentionally marked experimental with no active versions or performance metrics. The registry no longer fabricates models or evaluation numbers at startup. An artifact must be present, checksum-verified, and explicitly promoted before default inference can load it.

## Data and limitations

Training scripts include synthetic-data examples. Synthetic data does not establish external validity, calibration, subgroup performance, clinical utility, or safety. Dataset documentation describes NIH ChestX-ray14 and UCI Heart Disease, but no corresponding dataset payloads, licenses, trained weights, or reproducible evaluation bundle are checked in.

Preprocessing compatibility cannot be established without a model artifact and training provenance. No sensitivity, specificity, precision, recall, AUROC, PR-AUC, Brier score, expected calibration error, or subgroup result is claimed here.

## Explainability and uncertainty

Grad-CAM, SHAP, probability calibration, and uncertainty code exists, but no output from a real trained artifact was validated. Explanations are not proof of correctness or causal relevance. No confidence or risk score in this project should be interpreted clinically.

## Risk controls in this repository

- Missing active model artifacts fail closed; no random-weight fallback is created.
- Default loading requires an explicitly active version rather than falling back to the newest experiment.
- Promotion checks artifact presence and the recorded SHA-256 checksum.
- No clinical performance metric is published in the registry until evidence and provenance are available.

These code controls do not substitute for clinical, privacy, security, or regulatory review.
