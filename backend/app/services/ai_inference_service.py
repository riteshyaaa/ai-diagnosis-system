"""
MedFusion AI — AI Inference & Case Prediction Orchestration Service.

Coordinates:
- Case-triggered multimodal/unimodal AI inference execution
- Standalone real-time direct inference
- Relational mapping across DiagnosticCase, ImageRecord, and ClinicalRecord
- Integration with UnifiedInferenceService and ML Model Registry
- Persistence of PredictionRecord and ExplanationRecord (Grad-CAM & SHAP)
- Case lifecycle state transitions (PROCESSING -> COMPLETED)
- Cryptographic patient privacy protection (SHA-256 MRN hashing)
- Clinical uncertainty quantification & safety abstention enforcement
- HIPAA/GDPR immutable audit logging (INFERENCE_RUN, EXPLANATION_GENERATE)
- Non-autonomous CDSS regulatory compliance disclaimers
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
from app.exceptions import NotFoundError, ValidationError
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.diagnostic_case import CaseModality, CaseStatus, DiagnosticCase
from app.models.explanation_record import ExplanationRecord, ExplanationType
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
    """
    Production service orchestrating clinical AI inference, XAI artifact generation,
    and relational persistence for diagnostic cases.
    """

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
        Execute AI diagnostic prediction on an active case.

        - Resolves multimodal inputs (image radiograph and/or tabular measurements)
        - Executes unified multimodal inference pipeline with calibrated probabilities
        - Generates Grad-CAM visual heatmaps and SHAP feature attributions
        - Persists PredictionRecord and ExplanationRecord entities
        - Advances case workflow state to COMPLETED
        - Emits compliance audit log
        """
        # 1. Fetch case with full deep relations
        case = await self.case_repo.get_full_case_details(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        # 2. Transition case to PROCESSING state if active
        if case.status in (CaseStatus.DRAFT, CaseStatus.SUBMITTED):
            case.status = CaseStatus.PROCESSING
            await self.case_repo.update(case)

        # 3. Resolve Radiograph Image Input
        image_path: Optional[Path] = None
        selected_image_id: Optional[UUID] = request_data.selected_image_id

        if selected_image_id:
            image_record = await self.image_repo.get_by_id(selected_image_id)
            if not image_record or image_record.case_id != case_id:
                raise NotFoundError("ImageRecord", selected_image_id)
            image_path = await self.image_record_service.get_image_file_path(image_record.id, variant="processed")
        elif case.images:
            # Use most recently uploaded image for the case
            latest_image = case.images[-1]
            image_path = await self.image_record_service.get_image_file_path(latest_image.id, variant="processed")

        # 4. Resolve Structured Clinical EHR Input
        tabular_features: Optional[Dict[str, Any]] = None
        selected_clinical_id: Optional[UUID] = request_data.selected_clinical_record_id

        if selected_clinical_id:
            clinical_record = await self.clinical_repo.get_by_id(selected_clinical_id)
            if not clinical_record or clinical_record.case_id != case_id:
                raise NotFoundError("ClinicalRecord", selected_clinical_id)
            tabular_features = self._extract_tabular_dict(clinical_record)
        elif case.clinical_records:
            latest_clinical = case.clinical_records[-1]
            tabular_features = self._extract_tabular_dict(latest_clinical)

        # 5. Modality Validation
        if not image_path and not tabular_features:
            raise ValidationError(
                "Diagnostic case has no associated medical images or clinical records. "
                "Provide at least one input modality before running AI inference."
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
        ml_response: MLInferenceResponse = self.inference_engine.predict(ml_request)
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

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
        }

        # 11. Persist PredictionRecord
        model_version = request_data.model_version or ml_response.model_metadata.get("version", "1.0.0")
        prediction_entity = PredictionRecord(
            case_id=case.id,
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
        if ml_response.explainability:
            explanation_type = self._resolve_explanation_type(ml_response.modality)
            heatmap_path = await self._save_heatmap_file(saved_prediction.id, ml_response.explainability.gradcam_overlay_base64)
            shap_values, top_features = self._format_shap_artifacts(ml_response.explainability.shap_feature_contributions)
            summary_text = self._generate_clinical_summary(ml_response, primary_condition, cal_prob)

            explanation_entity = ExplanationRecord(
                prediction_id=saved_prediction.id,
                explanation_type=explanation_type,
                heatmap_path=heatmap_path,
                shap_values=shap_values,
                top_features=top_features,
                summary_text=summary_text,
            )
            saved_explanation = await self.explanation_repo.create(explanation_entity)
            saved_prediction.explanation = saved_explanation

            explainability_detail = ExplainabilityDetail(
                id=saved_explanation.id,
                explanation_type=explanation_type.value,
                heatmap_path=heatmap_path,
                heatmap_base64=ml_response.explainability.gradcam_heatmap_base64,
                overlay_base64=ml_response.explainability.gradcam_overlay_base64,
                shap_values=shap_values,
                top_features=top_features,
                summary_text=summary_text,
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
        ml_response: MLInferenceResponse = self.inference_engine.predict(ml_request)
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
        }

        # Format Explainability if available
        explainability_detail = None
        if ml_response.explainability:
            explanation_type = self._resolve_explanation_type(ml_response.modality)
            shap_values, top_features = self._format_shap_artifacts(ml_response.explainability.shap_feature_contributions)
            summary_text = self._generate_clinical_summary(ml_response, primary_condition, cal_prob)

            explainability_detail = ExplainabilityDetail(
                id=uuid.uuid4(),
                explanation_type=explanation_type.value,
                heatmap_path=None,
                heatmap_base64=ml_response.explainability.gradcam_heatmap_base64,
                overlay_base64=ml_response.explainability.gradcam_overlay_base64,
                shap_values=shap_values,
                top_features=top_features,
                summary_text=summary_text,
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
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

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
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        prediction = await self.prediction_repo.get_latest_by_case_id(case_id)
        if not prediction:
            raise NotFoundError("PredictionRecord for Case", case_id)

        return self._to_prediction_response(prediction)

    async def list_predictions(
        self,
        status: Optional[PredictionStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> PredictionListResponse:
        """List predictions with optional status filtering and pagination."""
        if status is not None:
            records = await self.prediction_repo.list_by_status(status=status, skip=skip, limit=limit)
        else:
            records = await self.prediction_repo.list_all(skip=skip, limit=limit)

        items = [self._to_prediction_response(p) for p in records]
        return PredictionListResponse(total=len(items), items=items)

    # --- Internal Helpers ---

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
    def _resolve_explanation_type(modality: InferenceModality) -> ExplanationType:
        """Map inference modality to database ExplanationType enum."""
        if modality == InferenceModality.MULTIMODAL:
            return ExplanationType.MULTIMODAL_ATTRIBUTION
        elif modality == InferenceModality.IMAGE_ONLY:
            return ExplanationType.GRADCAM_SALIENCY
        else:
            return ExplanationType.SHAP_FEATURE_IMPORTANCE

    @staticmethod
    def _resolve_primary_condition_and_probs(
        ml_response: MLInferenceResponse,
    ) -> tuple[str, float, float]:
        """Determine primary condition name, raw probability, and calibrated probability."""
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

    @staticmethod
    def _generate_clinical_summary(
        ml_response: MLInferenceResponse,
        primary_condition: str,
        calibrated_probability: float,
    ) -> str:
        """Formulate a concise, structured human-in-the-loop clinical interpretation summary."""
        parts = []
        if ml_response.modality == InferenceModality.MULTIMODAL:
            gating = ml_response.modality_gating
            img_w = gating.image_weight if gating else 0.5
            tab_w = gating.tabular_weight if gating else 0.5
            parts.append(
                f"MultimodalLateFusion evaluated: Visual Gating Weight = {img_w:.1%}, "
                f"Tabular Gating Weight = {tab_w:.1%}."
            )
            if ml_response.pathology_findings:
                pos_paths = [f"{f.pathology} ({f.probability:.1%})" for f in ml_response.pathology_findings if f.positive]
                if pos_paths:
                    parts.append(f"Detected radiograph findings: {', '.join(pos_paths)}.")
                else:
                    parts.append("No thoracic pathology findings exceeded the decision threshold.")
            if ml_response.clinical_risk:
                parts.append(
                    f"Cardiovascular risk assessed at {ml_response.clinical_risk.calibrated_probability:.1%} "
                    f"({ml_response.clinical_risk.risk_tier.value.upper()} risk tier)."
                )
        elif ml_response.modality == InferenceModality.IMAGE_ONLY:
            pos_paths = [f"{f.pathology} ({f.probability:.1%})" for f in ml_response.pathology_findings if f.positive]
            if pos_paths:
                parts.append(f"Chest radiograph visual evaluation identified: {', '.join(pos_paths)}.")
            else:
                parts.append("Chest radiograph visual evaluation found no findings above threshold.")
            parts.append("Grad-CAM visual saliency indicates anatomical activation regions for radiologist review.")
        else:
            if ml_response.clinical_risk:
                parts.append(
                    f"EHR tabular telemetry evaluation indicates {ml_response.clinical_risk.risk_tier.value.upper()} "
                    f"cardiovascular risk (calibrated probability: {ml_response.clinical_risk.calibrated_probability:.1%})."
                )
            if ml_response.explainability and ml_response.explainability.shap_feature_contributions:
                top_3 = [
                    f"{item['feature']} ({item['attribution']:+.2f})"
                    for item in ml_response.explainability.shap_feature_contributions[:3]
                ]
                parts.append(f"Top clinical feature contributors: {', '.join(top_3)}.")

        if ml_response.uncertainty.abstention_recommended:
            parts.append(f"NOTE: AI abstention triggered due to: {'; '.join(ml_response.uncertainty.abstention_reasons)}.")

        return " ".join(parts)

    def _to_prediction_response(
        self,
        record: PredictionRecord,
        explanation_override: Optional[ExplainabilityDetail] = None,
    ) -> PredictionResponse:
        """Convert a PredictionRecord ORM instance to a standard PredictionResponse schema."""
        detailed = record.detailed_predictions or {}
        pathology_findings = [
            PathologyDetail(**f) for f in detailed.get("pathology_findings", [])
        ]
        clinical_risk = (
            TabularRiskDetail(**detailed["clinical_risk"])
            if detailed.get("clinical_risk")
            else None
        )
        modality_gating = (
            ModalityGatingDetail(**detailed["modality_gating"])
            if detailed.get("modality_gating")
            else None
        )

        unc_dict = detailed.get("uncertainty", {})
        uncertainty = UncertaintyDetail(
            entropy=unc_dict.get("entropy", 0.0),
            confidence_score=unc_dict.get("confidence_score", record.confidence_score),
            confidence_band=unc_dict.get("confidence_band", record.confidence_band.value),
            cross_modal_conflict=unc_dict.get("cross_modal_conflict"),
            abstention_recommended=unc_dict.get("abstention_recommended", record.status == PredictionStatus.ABSTAINED),
            abstention_reasons=unc_dict.get(
                "abstention_reasons",
                [record.abstention_reason] if record.abstention_reason else [],
            ),
        )

        explanation_detail = explanation_override
        if explanation_detail is None and record.explanation is not None:
            explanation_detail = ExplainabilityDetail(
                id=record.explanation.id,
                explanation_type=record.explanation.explanation_type.value,
                heatmap_path=record.explanation.heatmap_path,
                shap_values=record.explanation.shap_values,
                top_features=record.explanation.top_features,
                summary_text=record.explanation.summary_text,
            )

        return PredictionResponse(
            id=record.id,
            case_id=record.case_id,
            model_type=record.model_type,
            model_version=record.model_version,
            primary_condition=record.primary_condition,
            raw_probability=record.raw_probability,
            calibrated_probability=record.calibrated_probability,
            confidence_score=record.confidence_score,
            confidence_band=record.confidence_band,
            status=record.status,
            abstention_reason=record.abstention_reason,
            detailed_predictions=detailed,
            pathology_findings=pathology_findings,
            clinical_risk=clinical_risk,
            modality_gating=modality_gating,
            uncertainty=uncertainty,
            inference_latency_ms=record.inference_latency_ms,
            explanation=explanation_detail,
            created_at=record.created_at,
        )
