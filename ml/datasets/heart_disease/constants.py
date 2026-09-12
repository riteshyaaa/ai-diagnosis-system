"""
MedFusion AI — UCI Heart Disease Clinical Constants & Physiological Reference Ranges.

Defines:
- Core 13 UCI Heart Disease feature specifications
- Clinical categorical encodings and human-readable descriptions
- Plausible physiological reference ranges and critical alert thresholds
"""

from enum import Enum, IntEnum
from typing import Any, Dict, List, NamedTuple, Optional


class SexEnum(IntEnum):
    FEMALE = 0
    MALE = 1


class ChestPainTypeEnum(IntEnum):
    TYPICAL_ANGINA = 0
    ATYPICAL_ANGINA = 1
    NON_ANGINAL = 2
    ASYMPTOMATIC = 3


class FastingBloodSugarEnum(IntEnum):
    NORMAL_LE_120 = 0
    ELEVATED_GT_120 = 1


class RestingECGEnum(IntEnum):
    NORMAL = 0
    ST_T_ABNORMALITY = 1
    LV_HYPERTROPHY = 2


class ExerciseAnginaEnum(IntEnum):
    NO = 0
    YES = 1


class STSlopeEnum(IntEnum):
    UPSLOPING = 0
    FLAT = 1
    DOWNSLOPING = 2


class ThalassemiaEnum(IntEnum):
    NORMAL = 1
    FIXED_DEFECT = 2
    REVERSIBLE_DEFECT = 3


class SmokingStatusEnum(str, Enum):
    NEVER = "never"
    FORMER = "former"
    CURRENT = "current"


class RangeSpec(NamedTuple):
    min_val: float
    max_val: float
    critical_low: Optional[float] = None
    critical_high: Optional[float] = None
    unit: str = ""


# Physiological validation boundaries for continuous clinical parameters
PHYSIOLOGICAL_RANGES: Dict[str, RangeSpec] = {
    "age": RangeSpec(min_val=1.0, max_val=125.0, critical_low=18.0, critical_high=95.0, unit="years"),
    "resting_bp": RangeSpec(min_val=50.0, max_val=260.0, critical_low=80.0, critical_high=180.0, unit="mm Hg"),
    "cholesterol": RangeSpec(min_val=80.0, max_val=600.0, critical_low=120.0, critical_high=350.0, unit="mg/dl"),
    "max_hr": RangeSpec(min_val=40.0, max_val=240.0, critical_low=50.0, critical_high=200.0, unit="bpm"),
    "st_depression": RangeSpec(min_val=-2.0, max_val=8.0, critical_low=None, critical_high=3.0, unit="mm"),
    "bmi": RangeSpec(min_val=10.0, max_val=75.0, critical_low=16.0, critical_high=40.0, unit="kg/m²"),
}

# Ordered list of the 13 core standard features for model alignment
CORE_FEATURE_NAMES: List[str] = [
    "age",
    "sex",
    "chest_pain_type",
    "resting_bp",
    "cholesterol",
    "fasting_bs",
    "resting_ecg",
    "max_hr",
    "exercise_angina",
    "st_depression",
    "st_slope",
    "num_major_vessels",
    "thalassemia",
]

CONTINUOUS_FEATURES: List[str] = [
    "age",
    "resting_bp",
    "cholesterol",
    "max_hr",
    "st_depression",
]

CATEGORICAL_FEATURES: List[str] = [
    "sex",
    "chest_pain_type",
    "fasting_bs",
    "resting_ecg",
    "exercise_angina",
    "st_slope",
    "num_major_vessels",
    "thalassemia",
]

# Baseline cohort population statistics (derived from UCI Heart Disease dataset) for imputation & scaling
DEFAULT_POPULATION_STATS: Dict[str, Dict[str, float]] = {
    "age": {"mean": 54.37, "std": 9.08, "median": 55.0},
    "resting_bp": {"mean": 131.62, "std": 17.54, "median": 130.0},
    "cholesterol": {"mean": 246.26, "std": 51.83, "median": 240.0},
    "max_hr": {"mean": 149.65, "std": 22.91, "median": 153.0},
    "st_depression": {"mean": 1.04, "std": 1.16, "median": 0.8},
}
