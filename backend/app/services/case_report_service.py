"""Build an owner-scoped report preview from persisted case records."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditAction, AuditResourceType
from app.models.clinical_record import ClinicalRecord
from app.models.clinical_review import ClinicalReview
from app.models.diagnostic_case import CaseModality, DiagnosticCase
from app.models.image_record import ImageRecord
from app.models.prediction_record import PredictionRecord
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.case_repository import CaseRepository
from app.schemas.clinical_review import CLINICAL_DISCLAIMER_TEXT
from app.schemas.report import (
    CaseReportPreviewResponse,
    ReportClinicalInput,
    ReportImageInput,
    ReportPatientSummary,
    ReportPredictionSummary,
    ReportReviewSummary,
    ReportStatus,
)
from app.security.record_access import require_case_owner

PROBABILITY_NOTICE = "Stored model scores are not verified as calibrated probabilities and are not clinical conclusions."
REPORT_PREVIEW_NOTICE = "This preview is not a finalized report. The prototype has no signature or controlled-delivery workflow."


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _latest_image(case: DiagnosticCase) -> Optional[ImageRecord]:
    return max(case.images, key=lambda image: image.created_at) if case.images else None


def _latest_clinical_record(case: DiagnosticCase) -> Optional[ClinicalRecord]:
    return (
        max(case.clinical_records, key=lambda record: record.updated_at)
        if case.clinical_records
        else None
    )


def _prediction_uses_current_inputs(
    case: DiagnosticCase,
    prediction: PredictionRecord,
    image: Optional[ImageRecord],
    clinical_record: Optional[ClinicalRecord],
) -> bool:
    uses_image = case.modality != CaseModality.TABULAR_ONLY
    uses_clinical = case.modality != CaseModality.IMAGE_ONLY

    image_matches = (
        prediction.image_record_id == (image.id if uses_image and image else None)
        and prediction.image_file_hash == (image.file_hash if uses_image and image else None)
        and (not uses_image or image is not None)
    )
    clinical_matches = (
        prediction.clinical_record_id
        == (clinical_record.id if uses_clinical and clinical_record else None)
        and _utc(prediction.clinical_record_updated_at)
        == _utc(clinical_record.updated_at if uses_clinical and clinical_record else None)
        and (not uses_clinical or clinical_record is not None)
    )
    return image_matches and clinical_matches


class CaseReportService:
    """Generate a non-final preview without persisting a report artifact."""

    def __init__(self, session: AsyncSession):
        self.case_repo = CaseRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def get_preview(
        self,
        case_id: UUID,
        viewer_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CaseReportPreviewResponse:
        case = require_case_owner(
            await self.case_repo.get_full_case_details(case_id), case_id, viewer_id
        )
        image = _latest_image(case)
        clinical_record = _latest_clinical_record(case)
        prediction = (
            max(case.predictions, key=lambda item: item.created_at) if case.predictions else None
        )

        current_inputs_match = bool(
            prediction and _prediction_uses_current_inputs(case, prediction, image, clinical_record)
        )
        current_review = None
        if prediction:
            reviews = [review for review in case.reviews if review.prediction_id == prediction.id]
            current_review = (
                max(reviews, key=lambda review: review.reviewed_at) if reviews else None
            )

        review_summary = self._review_summary(current_review)
        prediction_summary = self._prediction_summary(prediction, bool(current_inputs_match))
        patient = case.patient

        await self.audit_repo.log_event(
            action=AuditAction.CASE_VIEW,
            resource_type=AuditResourceType.CASE,
            resource_id=str(case.id),
            user_id=viewer_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"view_type": "report_preview"},
        )

        return CaseReportPreviewResponse(
            case_id=case.id,
            case_reference=case.case_number,
            generated_at=datetime.now(timezone.utc),
            status=(
                ReportStatus.PENDING_REVIEW
                if prediction_summary and prediction_summary.input_version_current
                else ReportStatus.DRAFT
            ),
            modality=case.modality,
            patient=ReportPatientSummary(
                age=patient.age if patient else None,
                sex=(patient.sex.value if patient and patient.sex else "unknown"),
            ),
            image_input=self._image_summary(image),
            clinical_input=self._clinical_summary(clinical_record),
            prediction=prediction_summary,
            review=review_summary,
            free_text_notes_included=False,
            probability_notice=PROBABILITY_NOTICE,
            disclaimer=f"{CLINICAL_DISCLAIMER_TEXT} {REPORT_PREVIEW_NOTICE}",
        )

    @staticmethod
    def _image_summary(image: Optional[ImageRecord]) -> Optional[ReportImageInput]:
        if image is None:
            return None
        return ReportImageInput(
            id=image.id,
            image_type=image.image_type,
            mime_type=image.mime_type,
            sha256=image.file_hash,
            width=image.width,
            height=image.height,
            created_at=image.created_at,
        )

    @staticmethod
    def _clinical_summary(
        clinical_record: Optional[ClinicalRecord],
    ) -> Optional[ReportClinicalInput]:
        if clinical_record is None:
            return None
        return ReportClinicalInput(
            id=clinical_record.id,
            updated_at=clinical_record.updated_at,
            age_years=clinical_record.age,
            sex_code=clinical_record.sex,
            chest_pain_type=clinical_record.chest_pain_type,
            resting_bp_mm_hg=clinical_record.resting_bp,
            cholesterol_mg_dl=clinical_record.cholesterol,
            fasting_bs=clinical_record.fasting_bs,
            resting_ecg=clinical_record.resting_ecg,
            max_hr_bpm=clinical_record.max_hr,
            exercise_angina=clinical_record.exercise_angina,
            st_depression_mm=clinical_record.st_depression,
            st_slope=clinical_record.st_slope,
            num_major_vessels=clinical_record.num_major_vessels,
            thalassemia=clinical_record.thalassemia,
            bmi=clinical_record.bmi,
            smoking_status=clinical_record.smoking_status,
        )

    @staticmethod
    def _prediction_summary(
        prediction: Optional[PredictionRecord], input_version_current: bool
    ) -> Optional[ReportPredictionSummary]:
        if prediction is None:
            return None
        explanation = prediction.explanation
        return ReportPredictionSummary(
            id=prediction.id,
            model_type=prediction.model_type,
            model_version=prediction.model_version,
            model_reported_finding=prediction.primary_condition,
            raw_score=prediction.raw_probability,
            stored_probability=prediction.calibrated_probability,
            confidence_score=prediction.confidence_score,
            confidence_band=prediction.confidence_band,
            status=prediction.status,
            abstention_reason=prediction.abstention_reason,
            image_record_id=prediction.image_record_id,
            image_sha256=prediction.image_file_hash,
            clinical_record_id=prediction.clinical_record_id,
            clinical_record_updated_at=prediction.clinical_record_updated_at,
            input_version_current=input_version_current,
            explanation_id=explanation.id if explanation else None,
            explanation_type=(explanation.explanation_type.value if explanation else None),
            created_at=prediction.created_at,
        )

    @staticmethod
    def _review_summary(review: Optional[ClinicalReview]) -> Optional[ReportReviewSummary]:
        if review is None:
            return None
        reviewer_role = None
        if review.reviewer and review.reviewer.role:
            reviewer_role = review.reviewer.role.value
        return ReportReviewSummary(
            id=review.id,
            prediction_id=review.prediction_id,
            reviewer_id=review.reviewer_id,
            reviewer_role=reviewer_role,
            decision=review.decision,
            modified_diagnosis=review.modified_diagnosis,
            rationale=review.clinical_notes,
            reviewed_at=review.reviewed_at,
        )
