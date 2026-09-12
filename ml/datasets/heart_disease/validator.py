"""
MedFusion AI — Clinical Tabular Feature Validator.

Validates:
- Physiological plausibility bounds (preventing biologically impossible entries)
- Categorical domain constraints (valid integer enum codes)
- Clinical risk alert triggers (hypertensive crisis, severe ST elevation/depression, tachycardia/bradycardia)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ml.datasets.heart_disease.constants import (
    CATEGORICAL_FEATURES,
    ChestPainTypeEnum,
    CONTINUOUS_FEATURES,
    ExerciseAnginaEnum,
    FastingBloodSugarEnum,
    PHYSIOLOGICAL_RANGES,
    RestingECGEnum,
    SexEnum,
    SmokingStatusEnum,
    STSlopeEnum,
    ThalassemiaEnum,
)


@dataclass
class ClinicalValidationReport:
    """Quantitative validation output for structured clinical measurements."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_features: Dict[str, Any] = field(default_factory=dict)


class ClinicalFeatureValidator:
    """Validates patient tabular measurements against clinical reference ranges."""

    @classmethod
    def validate(cls, raw_data: Dict[str, Any]) -> ClinicalValidationReport:
        """
        Validate clinical data dictionary.
        Returns a validation report with status, error list, warning list, and sanitized values.
        """
        errors: List[str] = []
        warnings: List[str] = []
        sanitized: Dict[str, Any] = {}

        # 1. Validate continuous features against physiological bounds
        for feat in CONTINUOUS_FEATURES:
            if feat not in raw_data or raw_data[feat] is None:
                errors.append(f"Missing required continuous feature: '{feat}'")
                continue

            try:
                val = float(raw_data[feat])
            except (ValueError, TypeError):
                errors.append(f"Feature '{feat}' must be a numerical value, got {raw_data[feat]}")
                continue

            range_spec = PHYSIOLOGICAL_RANGES.get(feat)
            if range_spec:
                # Plausibility check (hard rejection)
                if val < range_spec.min_val or val > range_spec.max_val:
                    errors.append(
                        f"Value {val} for '{feat}' is outside physiologically plausible range "
                        f"[{range_spec.min_val}, {range_spec.max_val}] {range_spec.unit}."
                    )
                else:
                    sanitized[feat] = val

                # Clinical warning thresholds
                if range_spec.critical_high and val >= range_spec.critical_high:
                    warnings.append(
                        f"CRITICAL HIGH: '{feat}' is {val} {range_spec.unit} (threshold: >={range_spec.critical_high})"
                    )
                elif range_spec.critical_low and val <= range_spec.critical_low:
                    warnings.append(
                        f"CRITICAL LOW: '{feat}' is {val} {range_spec.unit} (threshold: <={range_spec.critical_low})"
                    )
            else:
                sanitized[feat] = val

        # 2. Validate categorical features and allowable values
        cls._validate_categorical("sex", raw_data, [e.value for e in SexEnum], errors, sanitized)
        cls._validate_categorical(
            "chest_pain_type", raw_data, [e.value for e in ChestPainTypeEnum], errors, sanitized
        )
        cls._validate_categorical(
            "fasting_bs", raw_data, [e.value for e in FastingBloodSugarEnum], errors, sanitized
        )
        cls._validate_categorical(
            "resting_ecg", raw_data, [e.value for e in RestingECGEnum], errors, sanitized
        )
        cls._validate_categorical(
            "exercise_angina", raw_data, [e.value for e in ExerciseAnginaEnum], errors, sanitized
        )
        cls._validate_categorical(
            "st_slope", raw_data, [e.value for e in STSlopeEnum], errors, sanitized
        )
        cls._validate_categorical(
            "num_major_vessels", raw_data, [0, 1, 2, 3], errors, sanitized
        )
        cls._validate_categorical(
            "thalassemia", raw_data, [e.value for e in ThalassemiaEnum], errors, sanitized
        )

        # 3. Optional extended features
        if "bmi" in raw_data and raw_data["bmi"] is not None:
            try:
                bmi_val = float(raw_data["bmi"])
                bmi_spec = PHYSIOLOGICAL_RANGES["bmi"]
                if bmi_val < bmi_spec.min_val or bmi_val > bmi_spec.max_val:
                    errors.append(
                        f"BMI {bmi_val} is outside valid range [{bmi_spec.min_val}, {bmi_spec.max_val}]"
                    )
                else:
                    sanitized["bmi"] = bmi_val
                    if bmi_val >= bmi_spec.critical_high:
                        warnings.append(f"HIGH BMI (Class III Obesity): {bmi_val} kg/m²")
            except (ValueError, TypeError):
                errors.append(f"BMI must be a float, got {raw_data['bmi']}")

        if "smoking_status" in raw_data and raw_data["smoking_status"] is not None:
            smk = str(raw_data["smoking_status"]).lower()
            valid_statuses = [e.value for e in SmokingStatusEnum]
            if smk not in valid_statuses:
                errors.append(f"Invalid smoking_status '{smk}'. Must be one of: {valid_statuses}")
            else:
                sanitized["smoking_status"] = smk

        is_valid = len(errors) == 0
        return ClinicalValidationReport(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            sanitized_features=sanitized if is_valid else {},
        )

    @staticmethod
    def _validate_categorical(
        name: str,
        data: Dict[str, Any],
        allowed: List[int],
        errors: List[str],
        sanitized: Dict[str, Any],
    ) -> None:
        """Validate integer categorical code against allowed set."""
        if name not in data or data[name] is None:
            errors.append(f"Missing required categorical feature: '{name}'")
            return
        try:
            val = int(data[name])
            if val not in allowed:
                errors.append(
                    f"Feature '{name}' has value {val}, but must be one of allowable codes: {allowed}"
                )
            else:
                sanitized[name] = val
        except (ValueError, TypeError):
            errors.append(f"Feature '{name}' must be an integer, got {data[name]}")
