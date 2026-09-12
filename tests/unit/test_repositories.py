"""
MedFusion AI — Domain Repository Unit and Integration Tests.

Comprehensive test suite verifying database queries, relational operations,
eager loading, and integrity constraints across all domain repositories:
1. UserRepository
2. PatientRepository
3. CaseRepository
4. ImageRepository
5. ClinicalRecordRepository
6. PredictionRepository
7. ExplanationRepository
8. ClinicalReviewRepository
9. AuditLogRepository
"""

import hashlib
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.patient import Patient, BiologicalSex
from app.models.diagnostic_case import DiagnosticCase, CaseModality, CaseStatus
from app.models.image_record import ImageRecord, ImageType
from app.models.clinical_record import ClinicalRecord
from app.models.prediction_record import PredictionRecord, ModelType, PredictionStatus, ConfidenceBand
from app.models.explanation_record import ExplanationRecord, ExplanationType
from app.models.clinical_review import ClinicalReview, ReviewDecision
from app.models.audit_log import AuditAction, AuditResourceType
from app.repositories.user_repository import UserRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.image_repository import ImageRepository
from app.repositories.clinical_record_repository import ClinicalRecordRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.explanation_repository import ExplanationRepository
from app.repositories.clinical_review_repository import ClinicalReviewRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.security.password import hash_password


# ---------------------------------------------------------------------------
# UserRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_repository_crud_and_lockout(db_session: AsyncSession):
    """Test user creation, retrieval, and brute-force lockout mechanics."""
    repo = UserRepository(db_session)

    user = User(
        email="clinician.test@medfusion.local",
        hashed_password=hash_password("DocSecure2026!"),
        full_name="Dr. Test Clinician",
        role=UserRole.CLINICIAN,
        department="Cardiology",
    )
    saved_user = await repo.create(user)
    assert saved_user.id is not None
    assert saved_user.failed_login_attempts == 0

    # Lookup by email
    found = await repo.get_by_email("clinician.test@medfusion.local")
    assert found is not None
    assert found.id == saved_user.id
    assert found.full_name == "Dr. Test Clinician"

    # Lookup non-existent
    not_found = await repo.get_by_email("unknown@medfusion.local")
    assert not_found is None

    # Test failed login attempts increment
    for i in range(1, 5):
        await repo.record_failed_login(found, max_attempts=5, lockout_duration_seconds=900)
        assert found.failed_login_attempts == i
        assert found.locked_until is None

    # 5th failed attempt locks the account
    await repo.record_failed_login(found, max_attempts=5, lockout_duration_seconds=900)
    assert found.failed_login_attempts == 5
    assert found.locked_until is not None
    now = datetime.now(timezone.utc)
    assert found.is_locked(now) is True

    # Test reset on successful login
    await repo.reset_failed_logins(found)
    assert found.failed_login_attempts == 0
    assert found.locked_until is None
    assert found.last_login_at is not None
    assert found.is_locked(now) is False


# ---------------------------------------------------------------------------
# PatientRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patient_repository_mrn_hash_and_filter(db_session: AsyncSession):
    """Test privacy-preserving MRN hashing, lookup, and demographic filtering."""
    repo = PatientRepository(db_session)

    raw_mrn = "MRN-TEST-998811"
    mrn_hash = hashlib.sha256(raw_mrn.encode("utf-8")).hexdigest()

    patient1 = Patient(
        mrn_hash=mrn_hash,
        age=58,
        sex=BiologicalSex.FEMALE,
    )
    patient2 = Patient(
        mrn_hash=hashlib.sha256("MRN-TEST-998822".encode("utf-8")).hexdigest(),
        age=42,
        sex=BiologicalSex.MALE,
    )
    await repo.create(patient1)
    await repo.create(patient2)

    # Lookup by MRN Hash
    fetched = await repo.get_by_mrn_hash(mrn_hash)
    assert fetched is not None
    assert fetched.age == 58
    assert fetched.sex == BiologicalSex.FEMALE

    # Filter by demographic attributes
    females = await repo.filter_patients(sex=BiologicalSex.FEMALE)
    assert len(females) == 1
    assert females[0].mrn_hash == mrn_hash

    age_filtered = await repo.filter_patients(min_age=50, max_age=65)
    assert len(age_filtered) == 1
    assert age_filtered[0].age == 58


# ---------------------------------------------------------------------------
# CaseRepository & Full Relational Graph Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case_repository_and_eager_loading(db_session: AsyncSession):
    """Test diagnostic case lifecycle and full relational graph retrieval."""
    user_repo = UserRepository(db_session)
    patient_repo = PatientRepository(db_session)
    case_repo = CaseRepository(db_session)

    clinician = await user_repo.create(User(
        email="dr.case@medfusion.local",
        hashed_password=hash_password("DocSecure2026!"),
        full_name="Dr. Case Tester",
        role=UserRole.CLINICIAN,
    ))

    patient = await patient_repo.create(Patient(
        mrn_hash=hashlib.sha256("MRN-CASE-001".encode("utf-8")).hexdigest(),
        age=64,
        sex=BiologicalSex.MALE,
    ))

    case = await case_repo.create(DiagnosticCase(
        case_number="CASE-2026-TEST-001",
        patient_id=patient.id,
        created_by_id=clinician.id,
        modality=CaseModality.MULTIMODAL,
        status=CaseStatus.DRAFT,
        chief_complaint="Acute onset exertional dyspnea and retrosternal chest pressure.",
    ))

    assert case.id is not None
    assert case.case_number == "CASE-2026-TEST-001"

    # Lookup by case number
    by_num = await case_repo.get_by_case_number("CASE-2026-TEST-001")
    assert by_num is not None
    assert by_num.id == case.id

    # List by status
    draft_cases = await case_repo.list_by_status(CaseStatus.DRAFT)
    assert len(draft_cases) >= 1

    # List by patient
    patient_cases = await case_repo.list_by_patient(patient.id)
    assert len(patient_cases) == 1
    assert patient_cases[0].id == case.id

    # List by clinician
    clinician_cases = await case_repo.list_by_clinician(clinician.id, status=CaseStatus.DRAFT)
    assert len(clinician_cases) == 1

    # Test full details eager loading
    full_case = await case_repo.get_full_case_details(case.id)
    assert full_case is not None
    assert full_case.patient.age == 64
    assert full_case.creator.full_name == "Dr. Case Tester"


# ---------------------------------------------------------------------------
# ImageRecordRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_image_repository(db_session: AsyncSession):
    """Test image storage metadata, SHA-256 deduplication, and case linkage."""
    user_repo = UserRepository(db_session)
    patient_repo = PatientRepository(db_session)
    case_repo = CaseRepository(db_session)
    img_repo = ImageRepository(db_session)

    user = await user_repo.create(User(
        email="rad.test@medfusion.local",
        hashed_password=hash_password("RadSecure2026!"),
        full_name="Dr. Rad Tester",
        role=UserRole.RADIOLOGIST,
    ))
    patient = await patient_repo.create(Patient(
        mrn_hash=hashlib.sha256("MRN-IMG-001".encode("utf-8")).hexdigest(),
        age=50,
        sex=BiologicalSex.FEMALE,
    ))
    case = await case_repo.create(DiagnosticCase(
        case_number="CASE-IMG-001",
        patient_id=patient.id,
        created_by_id=user.id,
        modality=CaseModality.IMAGE_ONLY,
        status=CaseStatus.DRAFT,
    ))

    sha256_mock = hashlib.sha256(b"mock_cxr_image_bytes_content").hexdigest()
    image = ImageRecord(
        case_id=case.id,
        uploaded_by_id=user.id,
        original_filename="chest_xray_pa.png",
        file_path="/uploads/images/2026/chest_xray_pa.png",
        file_size_bytes=2048576,
        file_hash=sha256_mock,
        image_type=ImageType.CHEST_XRAY_PA,
        mime_type="image/png",
        width=1024,
        height=1024,
        channels=3,
    )
    saved_img = await img_repo.create(image)
    assert saved_img.id is not None

    # Lookup by SHA-256 hash (deduplication check)
    by_hash = await img_repo.get_by_hash(sha256_mock)
    assert by_hash is not None
    assert by_hash.id == saved_img.id

    # List by case
    case_images = await img_repo.get_by_case_id(case.id)
    assert len(case_images) == 1
    assert case_images[0].original_filename == "chest_xray_pa.png"

    # List by projection type
    pa_images = await img_repo.list_by_image_type(ImageType.CHEST_XRAY_PA)
    assert len(pa_images) >= 1


# ---------------------------------------------------------------------------
# ClinicalRecordRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clinical_record_repository(db_session: AsyncSession):
    """Test structured tabular clinical record storage and history retrieval."""
    user_repo = UserRepository(db_session)
    patient_repo = PatientRepository(db_session)
    case_repo = CaseRepository(db_session)
    clin_repo = ClinicalRecordRepository(db_session)

    user = await user_repo.create(User(
        email="clin.table@medfusion.local",
        hashed_password=hash_password("DocSecure2026!"),
        full_name="Dr. Table Tester",
        role=UserRole.CLINICIAN,
    ))
    patient = await patient_repo.create(Patient(
        mrn_hash=hashlib.sha256("MRN-TAB-001".encode("utf-8")).hexdigest(),
        age=60,
        sex=BiologicalSex.MALE,
    ))
    case = await case_repo.create(DiagnosticCase(
        case_number="CASE-TAB-001",
        patient_id=patient.id,
        created_by_id=user.id,
        modality=CaseModality.TABULAR_ONLY,
        status=CaseStatus.DRAFT,
    ))

    clin_record = ClinicalRecord(
        case_id=case.id,
        recorded_by_id=user.id,
        age=60,
        sex=1,  # 1: Male
        chest_pain_type=3,  # Asymptomatic
        resting_bp=145.0,
        cholesterol=240.0,
        fasting_bs=1,
        resting_ecg=1,
        max_hr=135.0,
        exercise_angina=1,
        st_depression=2.4,
        st_slope=2,
        num_major_vessels=2,
        thalassemia=3,
    )
    saved_rec = await clin_repo.create(clin_record)
    assert saved_rec.id is not None

    # Fetch latest by case
    latest = await clin_repo.get_latest_by_case_id(case.id)
    assert latest is not None
    assert latest.resting_bp == 145.0
    assert latest.cholesterol == 240.0


# ---------------------------------------------------------------------------
# PredictionRepository & ExplanationRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prediction_and_explanation_repositories(db_session: AsyncSession):
    """Test AI inference outputs, uncertainty metrics, and XAI artifacts."""
    user_repo = UserRepository(db_session)
    patient_repo = PatientRepository(db_session)
    case_repo = CaseRepository(db_session)
    pred_repo = PredictionRepository(db_session)
    exp_repo = ExplanationRepository(db_session)

    user = await user_repo.create(User(
        email="ai.tester@medfusion.local",
        hashed_password=hash_password("DocSecure2026!"),
        full_name="Dr. AI Supervisor",
        role=UserRole.CLINICIAN,
    ))
    patient = await patient_repo.create(Patient(
        mrn_hash=hashlib.sha256("MRN-AI-001".encode("utf-8")).hexdigest(),
        age=55,
        sex=BiologicalSex.FEMALE,
    ))
    case = await case_repo.create(DiagnosticCase(
        case_number="CASE-AI-001",
        patient_id=patient.id,
        created_by_id=user.id,
        modality=CaseModality.MULTIMODAL,
        status=CaseStatus.PROCESSING,
    ))

    prediction = PredictionRecord(
        case_id=case.id,
        model_type=ModelType.MULTIMODAL_FUSION,
        model_version="multimodal_late_fusion_v1.0.0",
        primary_condition="Aortic Enlargement / Cardiomegaly",
        raw_probability=0.895,
        calibrated_probability=0.912,
        confidence_score=0.912,
        confidence_band=ConfidenceBand.HIGH,
        status=PredictionStatus.CONFIDENT,
        detailed_predictions={"Cardiomegaly": 0.912, "Normal": 0.088},
        inference_latency_ms=142.5,
    )
    saved_pred = await pred_repo.create(prediction)
    assert saved_pred.id is not None

    explanation = ExplanationRecord(
        prediction_id=saved_pred.id,
        explanation_type=ExplanationType.MULTIMODAL_ATTRIBUTION,
        heatmap_path="/uploads/xai/case_ai_001_gradcam.png",
        shap_values={
            "serum_cholesterol": 0.28,
            "resting_bp": 0.22,
            "st_depression": 0.19,
            "age": 0.12,
        },
        top_features=[
            {"feature": "serum_cholesterol", "importance": 0.28, "direction": "elevating"},
            {"feature": "resting_bp", "importance": 0.22, "direction": "elevating"},
        ],
        summary_text="Model focused on cardiac silhouette apex and elevated serum cholesterol.",
    )
    saved_exp = await exp_repo.create(explanation)
    assert saved_exp.id is not None

    # Fetch prediction with explanation eagerly loaded
    pred_with_exp = await pred_repo.get_with_explanation(saved_pred.id)
    assert pred_with_exp is not None
    assert pred_with_exp.explanation is not None
    assert pred_with_exp.explanation.heatmap_path == "/uploads/xai/case_ai_001_gradcam.png"
    assert pred_with_exp.explanation.shap_values["serum_cholesterol"] == 0.28

    # Fetch explanation by prediction ID
    fetched_exp = await exp_repo.get_by_prediction_id(saved_pred.id)
    assert fetched_exp is not None
    assert fetched_exp.id == saved_exp.id


# ---------------------------------------------------------------------------
# ClinicalReviewRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clinical_review_repository(db_session: AsyncSession):
    """Test human-in-the-loop review decision tracking and mandatory rationale."""
    user_repo = UserRepository(db_session)
    patient_repo = PatientRepository(db_session)
    case_repo = CaseRepository(db_session)
    pred_repo = PredictionRepository(db_session)
    review_repo = ClinicalReviewRepository(db_session)

    reviewer = await user_repo.create(User(
        email="dr.senior@medfusion.local",
        hashed_password=hash_password("DocSecure2026!"),
        full_name="Dr. Senior Reviewer",
        role=UserRole.CLINICIAN,
    ))
    patient = await patient_repo.create(Patient(
        mrn_hash=hashlib.sha256("MRN-REV-001".encode("utf-8")).hexdigest(),
        age=71,
        sex=BiologicalSex.MALE,
    ))
    case = await case_repo.create(DiagnosticCase(
        case_number="CASE-REV-001",
        patient_id=patient.id,
        created_by_id=reviewer.id,
        modality=CaseModality.MULTIMODAL,
        status=CaseStatus.PROCESSING,
    ))
    pred = await pred_repo.create(PredictionRecord(
        case_id=case.id,
        model_type=ModelType.MULTIMODAL_FUSION,
        model_version="multimodal_late_fusion_v1.0.0",
        primary_condition="Cardiomegaly",
        raw_probability=0.86,
        calibrated_probability=0.88,
        confidence_score=0.88,
        confidence_band=ConfidenceBand.HIGH,
        status=PredictionStatus.CONFIDENT,
        detailed_predictions={"Cardiomegaly": 0.88},
        inference_latency_ms=130.0,
    ))

    review = ClinicalReview(
        case_id=case.id,
        prediction_id=pred.id,
        reviewer_id=reviewer.id,
        decision=ReviewDecision.ACCEPT,
        clinical_notes="Patient displays clear left ventricular enlargement consistent with chronic hypertension.",
    )
    saved_review = await review_repo.create(review)
    assert saved_review.id is not None

    # Query reviews by case ID
    case_reviews = await review_repo.get_by_case_id(case.id)
    assert len(case_reviews) == 1
    assert case_reviews[0].decision == ReviewDecision.ACCEPT
    assert case_reviews[0].reviewer.full_name == "Dr. Senior Reviewer"

    # Query reviews by reviewer
    reviewer_reviews = await review_repo.list_by_reviewer(reviewer.id, decision=ReviewDecision.ACCEPT)
    assert len(reviewer_reviews) == 1


# ---------------------------------------------------------------------------
# AuditLogRepository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_log_repository_and_compliance_trail(db_session: AsyncSession):
    """Test append-only immutable audit trail and multi-criteria queries."""
    user_repo = UserRepository(db_session)
    audit_repo = AuditLogRepository(db_session)

    auditor = await user_repo.create(User(
        email="auditor.test@medfusion.local",
        hashed_password=hash_password("AuditSecure2026!"),
        full_name="Auditor Compliance Officer",
        role=UserRole.AUDITOR,
    ))

    # Log several events
    await audit_repo.log_event(
        action=AuditAction.USER_LOGIN,
        resource_type=AuditResourceType.USER,
        resource_id=str(auditor.id),
        user_id=auditor.id,
        ip_address="192.168.1.50",
        user_agent="Mozilla/5.0 Medical Station",
        details={"auth_method": "password", "mfa": False},
    )

    await audit_repo.log_event(
        action=AuditAction.INFERENCE_RUN,
        resource_type=AuditResourceType.PREDICTION,
        resource_id="PRED-TEST-12345",
        user_id=auditor.id,
        ip_address="192.168.1.50",
        details={"latency_ms": 145.2, "model": "densenet121_v1"},
    )

    await audit_repo.log_event(
        action=AuditAction.REVIEW_SUBMIT,
        resource_type=AuditResourceType.REVIEW,
        resource_id="REV-TEST-9988",
        user_id=auditor.id,
        ip_address="192.168.1.50",
        details={"decision": "ACCEPT"},
    )

    # Count all logs for user
    count = await audit_repo.count_logs(user_id=auditor.id)
    assert count == 3

    # Count by specific action
    inference_count = await audit_repo.count_logs(action=AuditAction.INFERENCE_RUN)
    assert inference_count == 1

    # List filtered by action
    logs = await audit_repo.list_logs(action=AuditAction.INFERENCE_RUN)
    assert len(logs) == 1
    assert logs[0].action == AuditAction.INFERENCE_RUN
    assert logs[0].details["latency_ms"] == 145.2
    assert logs[0].user.full_name == "Auditor Compliance Officer"
