# MedFusion AI — Datasets Documentation

## Supported Datasets

### 1. NIH ChestX-ray14 (Imaging Modality)

- **Source**: NIH Clinical Center (108,948 frontal-view X-rays from 32,717 unique patients)
- **Target Conditions**: Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass, Nodule, Pneumonia, Pneumothorax, Consolidation, Edema, Emphysema, Fibrosis, Pleural Thickening, Hernia
- **Format**: PNG images (1024x1024 raw, resized to 224x224 for training) + `Data_Entry_2017.csv`
- **Data Splitting**: Patient-level splitting (all images from a single patient stay within one split: 70% train, 15% validation, 15% test) to prevent data leakage.

### 2. UCI Heart Disease (Tabular Modality)

- **Source**: UCI Machine Learning Repository (Cleveland, Hungarian, Switzerland, Long Beach V databases)
- **Features**: 13 clinical attributes (age, sex, chest pain type, resting blood pressure, cholesterol, fasting blood sugar, resting ECG, max heart rate, exercise-induced angina, ST depression, slope, number of major vessels, thal)
- **Target**: Presence of heart disease (binary: 0 = absent, 1 = present)
- **Preprocessing**: Median imputation for continuous features, mode imputation for categorical features, robust standard scaling.

### 3. Multimodal Dataset (Simulated / Paired)

- Paired imaging and clinical tabular data linked by synthetic or verified patient identifiers for training and evaluating the multimodal fusion architecture.
