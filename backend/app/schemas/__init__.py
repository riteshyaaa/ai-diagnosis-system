"""
MedFusion AI — Pydantic Schemas Package.
"""

from app.schemas.user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserPasswordChange,
    UserResponse,
)
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    TokenData,
)
from app.schemas.patient import (
    PatientBase,
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientListResponse,
)
from app.schemas.case import (
    CaseBase,
    CaseCreate,
    CaseUpdate,
    CaseStatusUpdate,
    CaseResponse,
    CaseDetailResponse,
    CaseListResponse,
    ImageRecordSummary,
    ClinicalRecordSummary,
    PredictionSummary,
    ExplanationSummary,
    ReviewSummary,
)
from app.schemas.image import (
    ImageQualityReportSchema,
    ImageRecordResponse,
    ImageUploadResponse,
    ImageListResponse,
)
from app.schemas.prediction import (
    CasePredictRequest,
    DirectPredictRequest,
    ExplainabilityDetail,
    ModalityGatingDetail,
    PathologyDetail,
    PredictionListResponse,
    PredictionResponse,
    TabularRiskDetail,
    UncertaintyDetail,
)
from app.schemas.explainability import (
    AttentionRegion,
    ExplanationListResponse,
    ExplanationResponse,
    FeatureAttributionItem,
    FeatureAttributionsResponse,
    RecalculatePathologySaliencyRequest,
    VisualExplanationResponse,
)
from app.schemas.clinical_review import (
    ClinicalReviewCreate,
    ClinicalReviewResponse,
    ClinicalReviewListResponse,
    ClinicalReviewStatsResponse,
    ReviewerSummary,
    ReviewDecision,
)

__all__ = [
    # User
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserPasswordChange",
    "UserResponse",
    # Auth
    "LoginRequest",
    "TokenResponse",
    "TokenRefreshRequest",
    "TokenData",
    # Patient
    "PatientBase",
    "PatientCreate",
    "PatientUpdate",
    "PatientResponse",
    "PatientListResponse",
    # Case
    "CaseBase",
    "CaseCreate",
    "CaseUpdate",
    "CaseStatusUpdate",
    "CaseResponse",
    "CaseDetailResponse",
    "CaseListResponse",
    "ImageRecordSummary",
    "ClinicalRecordSummary",
    "PredictionSummary",
    "ExplanationSummary",
    "ReviewSummary",
    # Image
    "ImageQualityReportSchema",
    "ImageRecordResponse",
    "ImageUploadResponse",
    "ImageListResponse",
    # Prediction
    "CasePredictRequest",
    "DirectPredictRequest",
    "ExplainabilityDetail",
    "ModalityGatingDetail",
    "PathologyDetail",
    "PredictionListResponse",
    "PredictionResponse",
    "TabularRiskDetail",
    "UncertaintyDetail",
    # Explainability
    "AttentionRegion",
    "ExplanationListResponse",
    "ExplanationResponse",
    "FeatureAttributionItem",
    "FeatureAttributionsResponse",
    "RecalculatePathologySaliencyRequest",
    "VisualExplanationResponse",
    # Clinical Review
    "ClinicalReviewCreate",
    "ClinicalReviewResponse",
    "ClinicalReviewListResponse",
    "ClinicalReviewStatsResponse",
    "ReviewerSummary",
    "ReviewDecision",
]
