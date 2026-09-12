"""
MedFusion AI — Unit Tests for Structured Clinical Tabular Pipeline.

Tests:
- ClinicalFeatureValidator (physiological boundaries, clinical alert triggers, categorical enums)
- HeartDiseasePreprocessor (NumPy vectorization, PyTorch FloatTensor encoding, One-Hot expansion, stats serialization)
"""

import json
import numpy as np
import pytest
import torch
from ml.datasets.heart_disease.constants import (
    CORE_FEATURE_NAMES,
    DEFAULT_POPULATION_STATS,
    ChestPainTypeEnum,
    SexEnum,
    STSlopeEnum,
    ThalassemiaEnum,
)
from ml.datasets.heart_disease.preprocessor import HeartDiseasePreprocessor
from ml.datasets.heart_disease.validator import (
    ClinicalFeatureValidator,
    ClinicalValidationReport,
)


@pytest.fixture
def valid_clinical_record():
    return {
        "age": 55,
        "sex": 1,
        "chest_pain_type": 2,
        "resting_bp": 130.0,
        "cholesterol": 240.0,
        "fasting_bs": 0,
        "resting_ecg": 1,
        "max_hr": 160.0,
        "exercise_angina": 0,
        "st_depression": 1.2,
        "st_slope": 1,
        "num_major_vessels": 0,
        "thalassemia": 2,
        "bmi": 26.5,
        "smoking_status": "former",
    }


def test_validator_accepts_valid_measurements(valid_clinical_record):
    """Verify validator accepts clinically plausible parameters."""
    report = ClinicalFeatureValidator.validate(valid_clinical_record)
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert len(report.sanitized_features) >= 13
    assert report.sanitized_features["age"] == 55.0
    assert report.sanitized_features["cholesterol"] == 240.0


def test_validator_rejects_implausible_continuous_values(valid_clinical_record):
    """Verify validator rejects impossible physiological measurements."""
    # Blood pressure > 260
    bad_bp = valid_clinical_record.copy()
    bad_bp["resting_bp"] = 350.0
    report_bp = ClinicalFeatureValidator.validate(bad_bp)
    assert report_bp.is_valid is False
    assert any("resting_bp" in err for err in report_bp.errors)

    # Negative heart rate
    bad_hr = valid_clinical_record.copy()
    bad_hr["max_hr"] = -10.0
    report_hr = ClinicalFeatureValidator.validate(bad_hr)
    assert report_hr.is_valid is False
    assert any("max_hr" in err for err in report_hr.errors)

    # Implausible cholesterol (< 80)
    bad_chol = valid_clinical_record.copy()
    bad_chol["cholesterol"] = 20.0
    report_chol = ClinicalFeatureValidator.validate(bad_chol)
    assert report_chol.is_valid is False


def test_validator_rejects_invalid_categorical_codes(valid_clinical_record):
    """Verify categorical constraints are enforced."""
    # Invalid sex code (only 0 or 1 allowed)
    bad_sex = valid_clinical_record.copy()
    bad_sex["sex"] = 5
    report = ClinicalFeatureValidator.validate(bad_sex)
    assert report.is_valid is False
    assert any("sex" in err for err in report.errors)

    # Invalid chest pain type (0-3 allowed)
    bad_cp = valid_clinical_record.copy()
    bad_cp["chest_pain_type"] = 9
    report_cp = ClinicalFeatureValidator.validate(bad_cp)
    assert report_cp.is_valid is False

    # Invalid thalassemia (1-3 allowed)
    bad_thal = valid_clinical_record.copy()
    bad_thal["thalassemia"] = 0
    report_thal = ClinicalFeatureValidator.validate(bad_thal)
    assert report_thal.is_valid is False


def test_validator_critical_clinical_warnings(valid_clinical_record):
    """Verify severe physiological thresholds trigger critical warnings."""
    critical_record = valid_clinical_record.copy()
    critical_record["resting_bp"] = 195.0  # Hypertensive crisis (>= 180)
    critical_record["st_depression"] = 3.5  # Severe ischemia (>= 3.0)
    critical_record["max_hr"] = 210.0  # Extreme tachycardia (>= 200)

    report = ClinicalFeatureValidator.validate(critical_record)
    assert report.is_valid is True
    assert len(report.warnings) >= 3
    assert any("CRITICAL HIGH: 'resting_bp'" in w for w in report.warnings)
    assert any("CRITICAL HIGH: 'st_depression'" in w for w in report.warnings)
    assert any("CRITICAL HIGH: 'max_hr'" in w for w in report.warnings)


def test_preprocessor_transform_dict(valid_clinical_record):
    """Verify conversion to normalized 1D NumPy array."""
    preprocessor = HeartDiseasePreprocessor()
    vec = preprocessor.transform_dict(valid_clinical_record, normalize_continuous=True)

    assert isinstance(vec, np.ndarray)
    assert vec.dtype == np.float32
    assert vec.shape == (13,)
    # Continuous features should be normalized (close to 0 on standard scale)
    assert -5.0 < vec[0] < 5.0  # Normalized age


def test_preprocessor_transform_to_tensor(valid_clinical_record):
    """Verify conversion to 2D PyTorch FloatTensor for late fusion."""
    preprocessor = HeartDiseasePreprocessor()

    # Single record
    tensor_single = preprocessor.transform_to_tensor(valid_clinical_record)
    assert isinstance(tensor_single, torch.Tensor)
    assert tensor_single.dtype == torch.float32
    assert tensor_single.shape == (1, 13)

    # Batch of records
    batch = [valid_clinical_record, valid_clinical_record]
    tensor_batch = preprocessor.transform_to_tensor(batch)
    assert tensor_batch.shape == (2, 13)


def test_preprocessor_one_hot_expansion(valid_clinical_record):
    """Verify 28-dimensional dense one-hot transformation."""
    preprocessor = HeartDiseasePreprocessor()
    one_hot_vec = preprocessor.transform_one_hot(valid_clinical_record)

    assert isinstance(one_hot_vec, np.ndarray)
    assert one_hot_vec.shape == (28,)
    # Check that one-hot slots sum to 1 for categorical groups
    # sex [idx 5, 6]
    assert np.sum(one_hot_vec[5:7]) == 1.0
    # chest_pain_type [idx 7, 8, 9, 10]
    assert np.sum(one_hot_vec[7:11]) == 1.0


def test_preprocessor_save_and_load_stats(tmp_path):
    """Verify preprocessor configuration persistence."""
    stats_file = tmp_path / "stats.json"
    preprocessor = HeartDiseasePreprocessor()
    preprocessor.save_stats(stats_file)

    assert stats_file.exists()
    loaded = HeartDiseasePreprocessor.load_stats(stats_file)
    assert loaded.stats == preprocessor.stats
