"""Prototype inference orchestration for supported diagnostic-case inputs.

The service persists model outputs and only the explanation artifacts actually returned.
It does not establish clinical validity, calibrated probabilities, or safety abstention.
"""

import base64
from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import ModelNotFoundError, NotFoundError, ValidationError
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.clinical_record import ClinicalRecord
from app.models.diagnostic_case import CaseModality, CaseStatus
from app.models.explanation_record import ExplanationRecord, ExplanationType
from app.models.image_record import ImageRecord
from app.models.prediction_record import (
    ConfidenceBand,
    ModelType,
    PredictionRecord,
    PredictionStatus,
)
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.clinical_record_repository import ClinicalRecordRepository
from app.repositories.explanation_repository import ExplanationRepository
from app.repositories.image_repository import ImageRepository
from app.repositories.prediction_repository import PredictionRepository
from app.security.record_access import require_case_owner
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
from app.services.image_record_service import ImageRecordService
from app.utils.prediction_mapping import prediction_record_to_response
from ml.inference.schemas import (
    InferenceModality,
    InferenceRequest,
    InferenceResponse as MLInferenceResponse,
)
from ml.inference.service import UnifiedInferenceService

logger = logging.getLogger(__name__)

# Global cached inference engine singleton
_inference_engine_instance: Optional[UnifiedInferenceService] = None


def get_inference_engine(device: Optional[str] = None) -> UnifiedInferenceService:
    """Retrieve or initialize the global UnifiedInferenceService singleton."""
    global _inference_engine_instance
    if _inference_engine_instance is None:
        settings = get_settings()
        dev = device or settings.inference_device
        _inference_engine_instance = UnifiedInferenceService(device=dev)
    return _inference_engine_instance


class AIInferenceService:
    """Prototype inference orchestration and persistence for diagnostic cases."""

    def __init__(
        self,
        session: AsyncSession,
        inference_engine: Optional[UnifiedInferenceService] = None,
    ):
        self.session = session
        self.prediction_repo = PredictionRepository(session)
        self.explanation_repo = ExplanationRepository(session)
        self.case_repo = CaseRepository(session)
        self.image_repo = ImageRepository(session)
        self.clinical_repo = ClinicalRecordRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.image_record_service = ImageRecordService(session)
        self.settings = get_settings()
        self.inference_engine = inference_engine or get_inference_engine(self.settings.inference_device)

    async def predict_case(
        self,
        case_id: UUID,
        request_data: CasePredictRequest,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PredictionResponse:
        """
        Request inference for explicitly supported inputs.

        - Selects the requested image and/or clinical record
        - Requests the active model for those inputs
        - Persists returned outputs and optional artifacts with exact input references
        - Leaves the case unchanged when model loading or inference fails
        - Writes an ordinary audit event, not a compliance certification
        """
        # 1. Fetch case with full deep relations
        case = await self.case_repo.get_full_case_details(case_id)
        case = require_case_owner(case, case_id, user_id)

        # 2. Resolve Radiograph Image Input
        image_path: Optional[Path] = None
        image_record: Optional[ImageRecord] = None
        selected_image_id: Optional[UUID] = request_data.selected_image_id
        if selected_image_id and case.modality == CaseModality.TABULAR_ONLY:
            raise ValidationError(
                "A tabular-only case cannot select an image input. Change the case modality first."
            )

        if selected_image_id:
            image_record = await self.image_repo.get_by_id(selected_image_id)
            if not image_record or image_record.case_id != case_id:
                raise NotFoundError("ImageRecord", selected_image_id)
            image_path = await self.image_record_service.get_image_file_path(
                image_record.id, variant="processed", viewer_id=user_id
            )
        elif case.images and case.modality != CaseModality.TABULAR_ONLY:
            # Use most recently uploaded image for the case
            latest_image = max(case.images, key=lambda image: image.created_at)
            image_record = latest_image
            image_path = await self.image_record_service.get_image_file_path(
                latest_image.id, variant="processed", viewer_id=user_id
            )
        # 4. Resolve Structured Clinical EHR Input
        tabular_features: Optional[Dict[str, Any]] = None
        clinical_record: Optional[ClinicalRecord] = None
        selected_clinical_id: Optional[UUID] = request_data.selected_clinical_record_id
        if selected_clinical_id and case.modality == CaseModality.IMAGE_ONLY:
            raise ValidationError(
                "An image-only case cannot select a clinical-record input. Change the case modality first."
            )

        if selected_clinical_id:
            clinical_record = await self.clinical_repo.get_by_id(selected_clinical_id)
            if not clinical_record or clinical_record.case_id != case_id:
                raise NotFoundError("ClinicalRecord", selected_clinical_id)
            tabular_features = self._extract_tabular_dict(clinical_record)
        elif case.clinical_records and case.modality != CaseModality.IMAGE_ONLY:
            clinical_record = max(
                case.clinical_records, key=lambda record: record.updated_at
            )
            tabular_features = self._extract_tabular_dict(clinical_record)
        # 5. Modality Validation
        if case.modality == CaseModality.IMAGE_ONLY and not image_path:
            raise ValidationError("An image-only case requires a supported image input.")
        if case.modality == CaseModality.TABULAR_ONLY and not tabular_features:
            raise ValidationError("A tabular-only case requires a clinical-record input.")
        if case.modality == CaseModality.MULTIMODAL and not image_path and not tabular_features:
            raise ValidationError("Case has no associated medical images or clinical records.")
        if case.modality == CaseModality.MULTIMODAL and (not image_path or not tabular_features):
            raise ValidationError(
                "A multimodal case requires both an image and a clinical-record input. "
                "Use an image-only or tabular-only case for a single-modality workflow."
            )

        # 6. Build ML Inference Request
        patient_mrn = case.patient.mrn_hash if case.patient else None
        ml_request = InferenceRequest(
            patient_mrn=patient_mrn,
            image_path=str(image_path) if image_path else None,
            tabular_features=tabular_features,
            generate_explainability=request_data.generate_explainability,
            model_version=request_data.model_version,
        )

        # 7. Execute Unified Model Inference
        start_time = time.perf_counter()
        ml_response = self._predict_or_raise_model_unavailable(ml_request)
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # Do not transition a case until inference succeeded. Missing weights must
        # leave the workflow state untouched rather than strand it as PROCESSING.
        if case.status in (CaseStatus.DRAFT, CaseStatus.SUBMITTED):
            case.status = CaseStatus.PROCESSING
            await self.case_repo.update(case)

        # 8. Extract Model Type and Primary Condition
        model_type = self._resolve_model_type(ml_response.modality)
        primary_condition, raw_prob, cal_prob = self._resolve_primary_condition_and_probs(ml_response)

        # 9. Map Uncertainty and Safety Status
        conf_band = ConfidenceBand(ml_response.uncertainty.confidence_band.value)
        if ml_response.uncertainty.abstention_recommended:
            status = PredictionStatus.ABSTAINED
        elif conf_band == ConfidenceBand.LOW:
            status = PredictionStatus.UNCERTAIN
        else:
            status = PredictionStatus.CONFIDENT

        abstention_reason = (
            "; ".join(ml_response.uncertainty.abstention_reasons)
            if ml_response.uncertainty.abstention_reasons
            else None
        )

        # 10. Construct Detailed Predictions Payload
        detailed_predictions: Dict[str, Any] = {
            "modality": ml_response.modality.value,
            "pathology_findings": [f.model_dump() for f in ml_response.pathology_findings],
            "clinical_risk": ml_response.clinical_risk.model_dump() if ml_response.clinical_risk else None,
            "modality_gating": ml_response.modality_gating.model_dump() if ml_response.modality_gating else None,
            "uncertainty": ml_response.uncertainty.model_dump(),
            "model_metadata": ml_response.model_metadata,
            "patient_mrn_hash": ml_response.patient_mrn_hash,
            "shap_base_value": (
                ml_response.explainability.shap_base_value
                if ml_response.explainability
                else None
            ),
        }

        # 11. Persist PredictionRecord
        model_version = request_data.model_version or ml_response.model_metadata.get("version", "1.0.0")
        prediction_entity = PredictionRecord(
            case_id=case.id,
            image_record_id=image_record.id if image_record else None,
            clinical_record_id=clinical_record.id if clinical_record else None,
            image_file_hash=image_record.file_hash if image_record else None,
            clinical_record_updated_at=(
                clinical_record.updated_at if clinical_record else None
            ),
            model_type=model_type,
            model_version=model_version,
            primary_condition=primary_condition,
            raw_probability=raw_prob,
            calibrated_probability=cal_prob,
            confidence_score=ml_response.uncertainty.confidence_score,
            confidence_band=conf_band,
            status=status,
            abstention_reason=abstention_reason,
            detailed_predictions=detailed_predictions,
            inference_latency_ms=latency_ms,
        )
        saved_prediction = await self.prediction_repo.create(prediction_entity)

        # 12. Persist Explainability Artifacts (Grad-CAM & SHAP)
        explanation_entity = None
        explainability_detail = None
        if ml_response.explainability and (
            ml_response.explainability.gradcam_heatmap_base64
            or ml_response.explainability.gradcam_overlay_base64
            or ml_response.explainability.shap_feature_contributions
        ):
            has_visual_artifact = bool(
                ml_response.explainability.gradcam_heatmap_base64
                or ml_response.explainability.gradcam_overlay_base64
            )
            has_tabular_artifact = bool(ml_response.explainability.shap_feature_contributions)
            explanation_type = self._resolve_explanation_type(
                has_visual_artifact,
                has_tabular_artifact,
            )
            heatmap_path = await self._save_heatmap_file(saved_prediction.id, ml_response.explainability.gradcam_overlay_base64)
            shap_values, top_features = self._format_shap_artifacts(ml_response.explainability.shap_feature_contributions)

            explanation_entity = ExplanationRecord(
                prediction_id=saved_prediction.id,
                explanation_type=explanation_type,
                heatmap_path=heatmap_path,
                shap_values=shap_values,
                top_features=top_features,
                summary_text=None,
            )
            saved_explanation = await self.explanation_repo.create(explanation_entity)
            saved_prediction.explanation = saved_explanation

            explainability_detail = ExplainabilityDetail(
                id=saved_explanation.id,
                explanation_type=explanation_type.value,
                heatmap_path=heatmap_path,
                heatmap_base64=ml_response.explainability.gradcam_heatmap_base64 or None,
                overlay_base64=ml_response.explainability.gradcam_overlay_base64 or None,
                shap_values=shap_values,
                top_features=top_features,
                summary_text=None,
            )

        # 13. Advance Case Status to COMPLETED
        if case.status in (CaseStatus.DRAFT, CaseStatus.SUBMITTED, CaseStatus.PROCESSING):
            case.status = CaseStatus.COMPLETED
            await self.case_repo.update(case)

        # 14. Compliance Audit Logging
        await self.audit_repo.log_event(
            action=AuditAction.INFERENCE_RUN,
            resource_type=AuditResourceType.PREDICTION,
            resource_id=str(saved_prediction.id),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "case_id": str(case.id),
                "model_type": model_type.value,
                "model_version": model_version,
                "primary_condition": primary_condition,
                "calibrated_probability": cal_prob,
                "confidence_band": conf_band.value,
                "status": status.value,
                "latency_ms": latency_ms,
                "abstention_recommended": ml_response.uncertainty.abstention_recommended,
            },
        )

        return self._to_prediction_response(saved_prediction, explanation_override=explainability_detail)

    async def predict_direct(
        self,
        request_data: DirectPredictRequest,
        image_bytes: Optional[bytes] = None,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PredictionResponse:
        """
        Execute standalone real-time inference without prior case persistence.
        """
        if image_bytes is None and not request_data.tabular_features:
            raise ValidationError("Direct inference requires either radiograph image bytes or tabular features.")

        ml_request = InferenceRequest(
            patient_mrn=request_data.patient_mrn,
            image_bytes=image_bytes,
            tabular_features=request_data.tabular_features,
            generate_explainability=request_data.generate_explainability,
            model_version=request_data.model_version,
        )

        start_time = time.perf_counter()
        ml_response = self._predict_or_raise_model_unavailable(ml_request)
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        model_type = self._resolve_model_type(ml_response.modality)
        primary_condition, raw_prob, cal_prob = self._resolve_primary_condition_and_probs(ml_response)
        conf_band = ConfidenceBand(ml_response.uncertainty.confidence_band.value)

        if ml_response.uncertainty.abstention_recommended:
            status = PredictionStatus.ABSTAINED
        elif conf_band == ConfidenceBand.LOW:
            status = PredictionStatus.UNCERTAIN
        else:
            status = PredictionStatus.CONFIDENT

        abstention_reason = (
            "; ".join(ml_response.uncertainty.abstention_reasons)
            if ml_response.uncertainty.abstention_reasons
            else None
        )

        detailed_predictions: Dict[str, Any] = {
            "modality": ml_response.modality.value,
            "pathology_findings": [f.model_dump() for f in ml_response.pathology_findings],
            "clinical_risk": ml_response.clinical_risk.model_dump() if ml_response.clinical_risk else None,
            "modality_gating": ml_response.modality_gating.model_dump() if ml_response.modality_gating else None,
            "uncertainty": ml_response.uncertainty.model_dump(),
            "model_metadata": ml_response.model_metadata,
            "patient_mrn_hash": ml_response.patient_mrn_hash,
            "shap_base_value": (
                ml_response.explainability.shap_base_value
                if ml_response.explainability
                else None
            ),
        }

        # Format Explainability if available
        explainability_detail = None
        if ml_response.explainability and (
            ml_response.explainability.gradcam_heatmap_base64
            or ml_response.explainability.gradcam_overlay_base64
            or ml_response.explainability.shap_feature_contributions
        ):
            has_visual_artifact = bool(
                ml_response.explainability.gradcam_heatmap_base64
                or ml_response.explainability.gradcam_overlay_base64
            )
            has_tabular_artifact = bool(ml_response.explainability.shap_feature_contributions)
            explanation_type = self._resolve_explanation_type(
                has_visual_artifact,
                has_tabular_artifact,
            )
            shap_values, top_features = self._format_shap_artifacts(ml_response.explainability.shap_feature_contributions)

            explainability_detail = ExplainabilityDetail(
                id=uuid.uuid4(),
                explanation_type=explanation_type.value,
                heatmap_path=None,
                heatmap_base64=ml_response.explainability.gradcam_heatmap_base64 or None,
                overlay_base64=ml_response.explainability.gradcam_overlay_base64 or None,
                shap_values=shap_values,
                top_features=top_features,
                summary_text=None,
            )

        # Audit direct inference
        await self.audit_repo.log_event(
            action=AuditAction.INFERENCE_RUN,
            resource_type=AuditResourceType.PREDICTION,
            resource_id="direct_inference",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "modality": ml_response.modality.value,
                "model_type": model_type.value,
                "primary_condition": primary_condition,
                "calibrated_probability": cal_prob,
                "confidence_band": conf_band.value,
                "status": status.value,
                "latency_ms": latency_ms,
            },
        )

        return PredictionResponse(
            id=uuid.uuid4(),
            case_id=None,
            model_type=model_type,
            model_version=request_data.model_version or ml_response.model_metadata.get("version", "1.0.0"),
            primary_condition=primary_condition,
            raw_probability=raw_prob,
            calibrated_probability=cal_prob,
            confidence_score=ml_response.uncertainty.confidence_score,
            confidence_band=conf_band,
            status=status,
            abstention_reason=abstention_reason,
            detailed_predictions=detailed_predictions,
            pathology_findings=[PathologyDetail(**f.model_dump()) for f in ml_response.pathology_findings],
            clinical_risk=TabularRiskDetail(**ml_response.clinical_risk.model_dump()) if ml_response.clinical_risk else None,
            modality_gating=ModalityGatingDetail(**ml_response.modality_gating.model_dump()) if ml_response.modality_gating else None,
            uncertainty=UncertaintyDetail(**ml_response.uncertainty.model_dump()),
            inference_latency_ms=latency_ms,
            explanation=explainability_detail,
            created_at=datetime.now(timezone.utc),
        )

    async def get_prediction(
        self,
        prediction_id: UUID,
        viewer_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PredictionResponse:
        """Fetch a specific prediction record with associated explanation."""
        prediction = await self.prediction_repo.get_with_explanation(prediction_id)
        if not prediction:
            raise NotFoundError("PredictionRecord", prediction_id)
        require_case_owner(
            await self.case_repo.get_by_id(prediction.case_id),
            prediction.case_id,
            viewer_id,
        )

        return self._to_prediction_response(prediction)

    async def get_case_predictions(
        self,
        case_id: UUID,
        viewer_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PredictionListResponse:
        """Fetch all predictions for a diagnostic case."""
        case = await self.case_repo.get_by_id(case_id)
        case = require_case_owner(case, case_id, viewer_id)

        predictions = await self.prediction_repo.get_by_case_id(case_id)
        items = [self._to_prediction_response(p) for p in predictions]
        return PredictionListResponse(total=len(items), items=items)

    async def get_latest_case_prediction(
        self,
        case_id: UUID,
        viewer_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PredictionResponse:
        """Fetch the most recent prediction for a diagnostic case."""
        case = await self.case_repo.get_by_id(case_id)
        case = require_case_owner(case, case_id, viewer_id)

        prediction = await self.prediction_repo.get_latest_by_case_id(case_id)
        if not prediction:
            raise NotFoundError("PredictionRecord for Case", case_id)

        return self._to_prediction_response(prediction)

    async def list_predictions(
        self,
        viewer_id: UUID,
        status: Optional[PredictionStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> PredictionListResponse:
        """List predictions with optional status filtering and pagination."""
        records, total = await self.prediction_repo.list_by_case_owner(
            owner_id=viewer_id,
            status=status,
            skip=skip,
            limit=limit,
        )

        items = [self._to_prediction_response(p) for p in records]
        return PredictionListResponse(total=total, items=items)

    # --- Internal Helpers ---

    def _predict_or_raise_model_unavailable(self, request: InferenceRequest) -> MLInferenceResponse:
        """Translate expected missing-artifact failures into a safe API 503."""
        try:
            return self.inference_engine.predict(request)
        except RuntimeError as exc:
            if "model not loaded in registry" in str(exc).lower():
                # Keep the public error stable and avoid returning internal model
                # registry details to API clients.
                raise ModelNotFoundError() from exc
            raise

    @staticmethod
    def _extract_tabular_dict(record: Any) -> Dict[str, Any]:
        """Extract valid clinical fields from a ClinicalRecord entity."""
        fields = [
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
        result = {}
        for f in fields:
            val = getattr(record, f, None)
            if val is not None:
                result[f] = val
        return result

    @staticmethod
    def _resolve_model_type(modality: InferenceModality) -> ModelType:
        """Map inference modality to database ModelType enum."""
        if modality == InferenceModality.MULTIMODAL:
            return ModelType.MULTIMODAL_FUSION
        elif modality == InferenceModality.IMAGE_ONLY:
            return ModelType.VISION_CLASSIFIER
        else:
            return ModelType.TABULAR_MLP

    @staticmethod
    def _resolve_explanation_type(
        has_visual_artifact: bool,
        has_tabular_artifact: bool,
    ) -> ExplanationType:
        """Describe only attribution artifacts actually generated for this prediction."""
        if has_visual_artifact and has_tabular_artifact:
            return ExplanationType.MULTIMODAL_ATTRIBUTION
        if has_visual_artifact:
            return ExplanationType.GRADCAM_SALIENCY
        return ExplanationType.SHAP_FEATURE_IMPORTANCE

    @staticmethod
    def _resolve_primary_condition_and_probs(
        ml_response: MLInferenceResponse,
    ) -> tuple[str, float, float]:
        """Map the primary condition and stored probability fields."""
        if ml_response.pathology_findings:
            top_pathology = max(ml_response.pathology_findings, key=lambda p: p.probability)
            if top_pathology.probability >= 0.5:
                primary = top_pathology.pathology
                raw = top_pathology.probability
                cal = top_pathology.calibrated_probability or top_pathology.probability
            elif ml_response.clinical_risk:
                primary = "Cardiovascular Disease Risk"
                raw = ml_response.clinical_risk.raw_probability
                cal = ml_response.clinical_risk.calibrated_probability
            else:
                primary = top_pathology.pathology
                raw = top_pathology.probability
                cal = top_pathology.calibrated_probability or top_pathology.probability
        elif ml_response.clinical_risk:
            primary = "Cardiovascular Disease Risk"
            raw = ml_response.clinical_risk.raw_probability
            cal = ml_response.clinical_risk.calibrated_probability
        else:
            primary = "Thoracic Pathology Evaluation"
            raw = 0.0
            cal = 0.0

        return primary, round(raw, 4), round(cal, 4)

    async def _save_heatmap_file(
        self,
        prediction_id: UUID,
        overlay_base64: Optional[str],
    ) -> Optional[str]:
        """Persist Grad-CAM overlay image to disk and return relative storage path."""
        if not overlay_base64:
            return None
        try:
            heatmaps_dir = Path(self.settings.upload_dir).resolve() / "heatmaps"
            heatmaps_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{prediction_id}_heatmap.png"
            target_path = heatmaps_dir / filename
            image_data = base64.b64decode(overlay_base64)
            with open(target_path, "wb") as f:
                f.write(image_data)
            return f"heatmaps/{filename}"
        except Exception as e:
            logger.warning("Failed to save heatmap file for prediction %s: %s", prediction_id, e)
            return None

    @staticmethod
    def _format_shap_artifacts(
        shap_contribs: Optional[List[Dict[str, Any]]],
    ) -> tuple[Optional[Dict[str, float]], Optional[List[Dict[str, Any]]]]:
        """Format SHAP contributions into dictionary mapping and ranked list."""
        if not shap_contribs:
            return None, None
        shap_dict = {item["feature"]: float(item["attribution"]) for item in shap_contribs}
        return shap_dict, shap_contribs

    def _to_prediction_response(
        self,
        record: PredictionRecord,
        explanation_override: Optional[ExplainabilityDetail] = None,
    ) -> PredictionResponse:
        """Convert a PredictionRecord ORM instance to a standard PredictionResponse schema."""
        return prediction_record_to_response(record, explanation_override)
