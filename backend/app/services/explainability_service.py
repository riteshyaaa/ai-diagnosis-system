"""
MedFusion AI — Clinical Explainability (XAI) Orchestration Service.

Comprehensive service managing:
- Grad-CAM visual saliency heatmaps and localized attention bounding boxes
- SHAP Tree/Kernel feature attribution waterfalls with physiological references
- Multimodal attribution fusing radiograph cues and clinical telemetry
- On-demand pathology saliency recalculation across thoracic conditions
- Secure file streaming of heatmap overlays with path traversal protection
- Immutable compliance audit logging (EXPLANATION_VIEW, EXPLANATION_GENERATE)
- Mandatory non-autonomous CDSS regulatory disclaimers
"""

import base64
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFoundError, ValidationError
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.explanation_record import ExplanationRecord, ExplanationType
from app.models.prediction_record import ModelType, PredictionRecord
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.explanation_repository import ExplanationRepository
from app.repositories.image_repository import ImageRepository
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.explainability import (
    CLINICAL_DISCLAIMER_TEXT,
    AttentionRegion,
    ExplanationListResponse,
    ExplanationResponse,
    FeatureAttributionItem,
    FeatureAttributionsResponse,
    RecalculatePathologySaliencyRequest,
    VisualExplanationResponse,
)
from app.schemas.prediction import ModalityGatingDetail
from app.services.ai_inference_service import get_inference_engine
from app.services.image_record_service import ImageRecordService
from ml.datasets.heart_disease.constants import CORE_FEATURE_NAMES
from ml.inference.service import TARGET_PATHOLOGIES, UnifiedInferenceService

logger = logging.getLogger(__name__)

# Medically calibrated clinical feature metadata with units, references, and interpretation
CLINICAL_FEATURE_METADATA: Dict[str, Dict[str, str]] = {
    "age": {
        "display_name": "Age (years)",
        "baseline_reference": "Standard baseline risk (< 55 yrs)",
        "interpretation": "Biological vascular aging and non-modifiable cardiovascular risk factor.",
    },
    "sex": {
        "display_name": "Biological Sex",
        "baseline_reference": "0: Female, 1: Male",
        "interpretation": "Demographic risk weighting reflecting epidemiological cardiovascular variance.",
    },
    "chest_pain_type": {
        "display_name": "Chest Pain Classification",
        "baseline_reference": "0: Typical, 1: Atypical, 2: Non-anginal, 3: Asymptomatic",
        "interpretation": "Symptom presentation and ischemic chest discomfort characteristics.",
    },
    "resting_bp": {
        "display_name": "Resting Blood Pressure (mmHg)",
        "baseline_reference": "Normal: < 120 mmHg (Stage 1/2 HTN >= 130 mmHg)",
        "interpretation": "Systemic arterial pressure contributing to left ventricular afterload.",
    },
    "cholesterol": {
        "display_name": "Serum Cholesterol (mg/dL)",
        "baseline_reference": "Desirable: < 200 mg/dL (Borderline: 200-239, High >= 240)",
        "interpretation": "Circulating atherogenic lipid levels associated with coronary plaque accumulation.",
    },
    "fasting_bs": {
        "display_name": "Fasting Blood Sugar (> 120 mg/dL)",
        "baseline_reference": "Normal: <= 120 mg/dL (0: Normal, 1: Elevated)",
        "interpretation": "Metabolic and diabetic risk indicator linked to macrovascular pathology.",
    },
    "resting_ecg": {
        "display_name": "Resting Electrocardiogram",
        "baseline_reference": "0: Normal, 1: ST-T Wave Abnormality, 2: LV Hypertrophy",
        "interpretation": "Baseline cardiac electrical conduction and repolarization morphology.",
    },
    "max_hr": {
        "display_name": "Maximum Heart Rate Achieved (bpm)",
        "baseline_reference": "Age-predicted max: ~220 - Age (Normal > 140 bpm)",
        "interpretation": "Chronotropic functional capacity during cardiovascular stress workload.",
    },
    "exercise_angina": {
        "display_name": "Exercise-Induced Angina",
        "baseline_reference": "0: Absent, 1: Provoked by Exertion",
        "interpretation": "Direct indicator of exercise-induced transient myocardial ischemia.",
    },
    "st_depression": {
        "display_name": "ST-Segment Depression (mm)",
        "baseline_reference": "Normal: 0.0 mm (Ischemic threshold >= 1.0 mm)",
        "interpretation": "Electrocardiographic subendocardial ischemia induced by exercise workload.",
    },
    "st_slope": {
        "display_name": "Peak Exercise ST Slope",
        "baseline_reference": "0: Upsloping (normal), 1: Flat, 2: Downsloping",
        "interpretation": "ST segment morphology reflecting recovery kinetics and coronary insufficiency.",
    },
    "num_major_vessels": {
        "display_name": "Major Vessels Colored by Fluoroscopy (0-3)",
        "baseline_reference": "Normal: 0 vessels with >50% luminal stenosis",
        "interpretation": "Anatomical burden of obstructive coronary artery disease.",
    },
    "thalassemia": {
        "display_name": "Thallium Stress Scintigraphy",
        "baseline_reference": "1: Normal, 2: Fixed Defect (infarct), 3: Reversible Defect (ischemia)",
        "interpretation": "Nuclear myocardial perfusion imaging evaluating fixed scar vs viable ischemia.",
    },
}


class ExplainabilityService:
    """
    Core service managing explainability artifacts, visual Grad-CAM overlays,
    SHAP feature attribution waterfalls, and on-demand recalculation.
    """

    def __init__(
        self,
        session: AsyncSession,
        inference_engine: Optional[UnifiedInferenceService] = None,
    ):
        self.session = session
        self.explanation_repo = ExplanationRepository(session)
        self.prediction_repo = PredictionRepository(session)
        self.case_repo = CaseRepository(session)
        self.image_repo = ImageRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.image_record_service = ImageRecordService(session)
        self.settings = get_settings()
        self.inference_engine = inference_engine or get_inference_engine(self.settings.inference_device)

    async def get_explanation_by_prediction_id(
        self,
        prediction_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ExplanationResponse:
        """
        Fetch full composite explainability record for a given prediction.
        Constructs visual Grad-CAM responses, SHAP feature waterfalls, and modality gating weights.
        """
        prediction = await self.prediction_repo.get_by_id(prediction_id)
        if not prediction:
            raise NotFoundError("PredictionRecord", prediction_id)

        explanation = prediction.explanation
        if not explanation:
            # Check if explanation exists independently in repository
            explanation = await self.explanation_repo.get_by_prediction_id(prediction_id)

        if not explanation:
            raise NotFoundError("ExplanationRecord", prediction_id)

        # Build Visual Explanation
        visual_explanation = self._build_visual_explanation(prediction, explanation)

        # Build Tabular Explanation
        tabular_explanation = self._build_tabular_explanation(prediction, explanation)

        # Build Modality Gating
        modality_gating = self._extract_modality_gating(prediction)

        # Audit Logging
        await self.audit_repo.log_event(
            action=AuditAction.EXPLANATION_VIEW,
            resource_type=AuditResourceType.EXPLANATION,
            resource_id=str(explanation.id),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "prediction_id": str(prediction.id),
                "case_id": str(prediction.case_id) if prediction.case_id else None,
                "explanation_type": explanation.explanation_type.value,
            },
        )

        return ExplanationResponse(
            id=explanation.id,
            prediction_id=prediction.id,
            case_id=prediction.case_id,
            explanation_type=explanation.explanation_type.value,
            model_type=prediction.model_type.value,
            primary_condition=prediction.primary_condition,
            calibrated_probability=prediction.calibrated_probability,
            confidence_band=prediction.confidence_band.value,
            visual_explanation=visual_explanation,
            tabular_explanation=tabular_explanation,
            modality_gating=modality_gating,
            summary_text=explanation.summary_text,
            clinical_disclaimer=CLINICAL_DISCLAIMER_TEXT,
            created_at=explanation.created_at,
        )

    async def get_heatmap_file_path(
        self,
        prediction_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Path:
        """
        Securely resolve the absolute on-disk path to the Grad-CAM heatmap overlay image.
        Guards against directory traversal attacks.
        """
        prediction = await self.prediction_repo.get_by_id(prediction_id)
        if not prediction:
            raise NotFoundError("PredictionRecord", prediction_id)

        explanation = prediction.explanation or await self.explanation_repo.get_by_prediction_id(prediction_id)
        if not explanation or not explanation.heatmap_path:
            raise NotFoundError("GradCAMHeatmap", prediction_id)

        # Resolve relative or absolute artifact paths safely
        # Storage directory may contain relative subpaths (e.g., ./uploads/heatmaps/)
        raw_path = Path(explanation.heatmap_path)
        # If relative, anchor under storage_dir; if absolute, verify under storage_dir
        if raw_path.is_absolute():
            resolved_path = raw_path.resolve()
        else:
            storage_base = Path(self.settings.upload_dir).resolve()
            resolved_path = (storage_base / raw_path).resolve()

        # Path traversal guard
        storage_base = Path(self.settings.upload_dir).resolve()
        try:
            resolved_path.relative_to(storage_base)
        except ValueError:
            logger.warning("Path traversal attempt detected for heatmap: %s", explanation.heatmap_path)
            raise ValidationError("Invalid artifact file location.")

        if not resolved_path.exists() or not resolved_path.is_file():
            raise NotFoundError("HeatmapImageFile", prediction_id)

        # Audit Logging
        await self.audit_repo.log_event(
            action=AuditAction.EXPLANATION_VIEW,
            resource_type=AuditResourceType.IMAGE,
            resource_id=str(explanation.id),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"prediction_id": str(prediction_id), "heatmap_path": str(resolved_path)},
        )

        return resolved_path

    async def get_tabular_feature_attributions(
        self,
        prediction_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> FeatureAttributionsResponse:
        """
        Fetch structured SHAP feature attribution waterfall and ranked drivers.
        """
        prediction = await self.prediction_repo.get_by_id(prediction_id)
        if not prediction:
            raise NotFoundError("PredictionRecord", prediction_id)

        explanation = prediction.explanation or await self.explanation_repo.get_by_prediction_id(prediction_id)
        if not explanation or not explanation.shap_values:
            raise NotFoundError("FeatureAttributions", prediction_id)

        tabular_explanation = self._build_tabular_explanation(prediction, explanation)
        if not tabular_explanation:
            raise NotFoundError("FeatureAttributions", prediction_id)

        # Audit Logging
        await self.audit_repo.log_event(
            action=AuditAction.EXPLANATION_VIEW,
            resource_type=AuditResourceType.EXPLANATION,
            resource_id=str(explanation.id),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"prediction_id": str(prediction_id), "features_count": tabular_explanation.total_features_evaluated},
        )

        return tabular_explanation

    async def get_explanations_by_case_id(
        self,
        case_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ExplanationListResponse:
        """
        Retrieve all historical explainability records generated for a diagnostic case.
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("DiagnosticCase", case_id)

        explanations = await self.explanation_repo.get_by_case_id(case_id)
        items: List[ExplanationResponse] = []

        for expl in explanations:
            prediction = await self.prediction_repo.get_by_id(expl.prediction_id)
            if not prediction:
                continue

            visual_explanation = self._build_visual_explanation(prediction, expl)
            tabular_explanation = self._build_tabular_explanation(prediction, expl)
            modality_gating = self._extract_modality_gating(prediction)

            items.append(
                ExplanationResponse(
                    id=expl.id,
                    prediction_id=prediction.id,
                    case_id=prediction.case_id,
                    explanation_type=expl.explanation_type.value,
                    model_type=prediction.model_type.value,
                    primary_condition=prediction.primary_condition,
                    calibrated_probability=prediction.calibrated_probability,
                    confidence_band=prediction.confidence_band.value,
                    visual_explanation=visual_explanation,
                    tabular_explanation=tabular_explanation,
                    modality_gating=modality_gating,
                    summary_text=expl.summary_text,
                    clinical_disclaimer=CLINICAL_DISCLAIMER_TEXT,
                    created_at=expl.created_at,
                )
            )

        # Audit Logging
        await self.audit_repo.log_event(
            action=AuditAction.EXPLANATION_VIEW,
            resource_type=AuditResourceType.EXPLANATION,
            resource_id=str(case_id),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"case_id": str(case_id), "count": len(items)},
        )

        return ExplanationListResponse(total=len(items), items=items)

    async def recalculate_pathology_saliency(
        self,
        prediction_id: UUID,
        request_data: RecalculatePathologySaliencyRequest,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> VisualExplanationResponse:
        """
        Recompute Grad-CAM visual saliency on-demand for an alternative thoracic pathology
        (e.g., Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass).
        """
        target_pathology = request_data.target_pathology.strip()
        if target_pathology not in TARGET_PATHOLOGIES:
            raise ValidationError(
                f"Unknown target pathology '{target_pathology}'. "
                f"Supported pathologies are: {', '.join(TARGET_PATHOLOGIES)}"
            )

        prediction = await self.prediction_repo.get_by_id(prediction_id)
        if not prediction:
            raise NotFoundError("PredictionRecord", prediction_id)

        # Resolve Image Path
        image_path: Optional[Path] = None
        if prediction.case_id:
            case = await self.case_repo.get_full_case_details(prediction.case_id)
            if case and case.images:
                latest_img = case.images[-1]
                image_path = await self.image_record_service.get_image_file_path(latest_img.id, variant="processed")

        if not image_path or not image_path.exists():
            raise ValidationError("Prediction has no associated processed radiograph image for saliency recalculation.")

        # Execute Grad-CAM Recalculation
        heatmap_b64, overlay_b64, raw_boxes = self.inference_engine.explain_pathology(
            image_input=image_path,
            target_pathology=target_pathology,
            target_layer=request_data.target_layer,
        )

        attention_regions = self._convert_bounding_boxes_to_attention_regions(raw_boxes, target_pathology)

        summary_text = (
            f"On-demand Grad-CAM visual saliency recalculated for {target_pathology}. "
            f"Identified {len(attention_regions)} localized focal activation region(s) "
            f"above 60% activation threshold."
        )

        # Audit Logging
        await self.audit_repo.log_event(
            action=AuditAction.EXPLANATION_RECALCULATE,
            resource_type=AuditResourceType.EXPLANATION,
            resource_id=str(prediction_id),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "prediction_id": str(prediction_id),
                "target_pathology": target_pathology,
                "attention_regions_count": len(attention_regions),
            },
        )

        return VisualExplanationResponse(
            prediction_id=prediction.id,
            case_id=prediction.case_id,
            target_pathology=target_pathology,
            heatmap_url=f"/api/v1/predictions/{prediction.id}/heatmap",
            overlay_url=f"/api/v1/predictions/{prediction.id}/heatmap",
            overlay_base64=overlay_b64,
            heatmap_base64=heatmap_b64,
            attention_regions=attention_regions,
            summary_text=summary_text,
            clinical_disclaimer=CLINICAL_DISCLAIMER_TEXT,
        )

    # -------------------------------------------------------------------------
    # Internal Helpers & Transformers
    # -------------------------------------------------------------------------

    def _build_visual_explanation(
        self,
        prediction: PredictionRecord,
        explanation: ExplanationRecord,
    ) -> Optional[VisualExplanationResponse]:
        """Construct structured VisualExplanationResponse from database models."""
        if explanation.explanation_type == ExplanationType.SHAP_FEATURE_IMPORTANCE:
            return None

        heatmap_url = f"/api/v1/predictions/{prediction.id}/heatmap" if explanation.heatmap_path else None
        overlay_url = heatmap_url

        detailed = prediction.detailed_predictions or {}
        findings = detailed.get("pathology_findings", [])
        target_pathology = prediction.primary_condition
        if findings and not target_pathology:
            target_pathology = findings[0].get("pathology", "Cardiomegaly")

        # Extract attention regions from detailed predictions or generate from top features
        attention_regions: List[AttentionRegion] = []
        raw_boxes = detailed.get("bounding_boxes", [])
        if raw_boxes:
            attention_regions = self._convert_bounding_boxes_to_attention_regions(raw_boxes, target_pathology)
        elif explanation.heatmap_path:
            # Provide standard anatomical field bounding box if heatmap exists
            attention_regions.append(
                AttentionRegion(
                    box=[0.20, 0.20, 0.80, 0.80],
                    saliency_score=round(prediction.calibrated_probability, 3),
                    anatomical_region="Thoracic Cavity & Cardiac Silhouette",
                    associated_pathology=target_pathology,
                )
            )

        return VisualExplanationResponse(
            prediction_id=prediction.id,
            case_id=prediction.case_id,
            target_pathology=target_pathology or "Thoracic Radiograph Evaluation",
            heatmap_url=heatmap_url,
            overlay_url=overlay_url,
            overlay_base64=detailed.get("overlay_base64"),
            heatmap_base64=detailed.get("heatmap_base64"),
            attention_regions=attention_regions,
            summary_text=explanation.summary_text,
            clinical_disclaimer=CLINICAL_DISCLAIMER_TEXT,
        )

    def _build_tabular_explanation(
        self,
        prediction: PredictionRecord,
        explanation: ExplanationRecord,
    ) -> Optional[FeatureAttributionsResponse]:
        """Construct structured FeatureAttributionsResponse with clinical interpretation."""
        if explanation.explanation_type == ExplanationType.GRADCAM_SALIENCY:
            return None

        shap_map = explanation.shap_values or {}
        if not shap_map:
            return None

        detailed = prediction.detailed_predictions or {}
        clinical_risk = detailed.get("clinical_risk") or {}
        base_value = float(clinical_risk.get("base_value", 0.5))
        predicted_risk = float(prediction.calibrated_probability)

        # Extract observed patient feature values if available
        observed_values: Dict[str, Any] = detailed.get("tabular_features", {})

        # Compute total absolute impact for percentage normalization
        total_abs_shap = sum(abs(v) for v in shap_map.values()) or 1.0

        all_items: List[FeatureAttributionItem] = []
        for feature_key, shap_val in shap_map.items():
            meta = CLINICAL_FEATURE_METADATA.get(
                feature_key,
                {
                    "display_name": feature_key.replace("_", " ").title(),
                    "baseline_reference": "Standard Clinical Reference",
                    "interpretation": f"Contribution of {feature_key} to risk estimation.",
                },
            )

            direction = "risk_increasing" if shap_val > 0 else "risk_decreasing"
            pct_impact = round((abs(shap_val) / total_abs_shap) * 100.0, 2)
            observed_val = observed_values.get(feature_key)

            all_items.append(
                FeatureAttributionItem(
                    feature_name=feature_key,
                    display_name=meta["display_name"],
                    feature_value=observed_val,
                    baseline_reference=meta["baseline_reference"],
                    shap_value=round(float(shap_val), 4),
                    importance_rank=1,  # Calculated after sorting
                    direction=direction,
                    percentage_impact=pct_impact,
                    clinical_interpretation=meta["interpretation"],
                )
            )

        # Sort by absolute SHAP magnitude descending
        all_items.sort(key=lambda x: abs(x.shap_value), reverse=True)
        for idx, item in enumerate(all_items, start=1):
            item.importance_rank = idx

        top_increasing = [item for item in all_items if item.direction == "risk_increasing"]
        top_decreasing = [item for item in all_items if item.direction == "risk_decreasing"]

        return FeatureAttributionsResponse(
            prediction_id=prediction.id,
            case_id=prediction.case_id,
            model_type=prediction.model_type.value,
            base_value=base_value,
            predicted_risk=predicted_risk,
            total_features_evaluated=len(all_items),
            top_risk_increasing_features=top_increasing[:5],
            top_risk_decreasing_features=top_decreasing[:5],
            all_features=all_items,
            summary_text=explanation.summary_text,
            clinical_disclaimer=CLINICAL_DISCLAIMER_TEXT,
        )

    @staticmethod
    def _extract_modality_gating(prediction: PredictionRecord) -> Optional[ModalityGatingDetail]:
        """Extract late-fusion modality gating weights from prediction payload."""
        detailed = prediction.detailed_predictions or {}
        gating_dict = detailed.get("modality_gating")
        if not gating_dict:
            return None

        return ModalityGatingDetail(
            image_weight=gating_dict.get("image_weight", 0.5),
            tabular_weight=gating_dict.get("tabular_weight", 0.5),
            dominant_modality=gating_dict.get("dominant_modality", "balanced"),
        )

    @staticmethod
    def _convert_bounding_boxes_to_attention_regions(
        raw_boxes: List[Dict[str, Any]],
        pathology_name: str,
    ) -> List[AttentionRegion]:
        """Convert pixel-based or normalized bounding boxes to AttentionRegion schemas."""
        regions: List[AttentionRegion] = []
        for b in raw_boxes:
            # Handle normalized box [ymin, xmin, ymax, xmax] or dict {x, y, width, height}
            if isinstance(b, dict):
                x = b.get("x", 0)
                y = b.get("y", 0)
                w = b.get("width", 50)
                h = b.get("height", 50)
                # Normalize assuming standard 256x256 resolution if > 1.0
                norm_x = x / 256.0 if x > 1.0 else x
                norm_y = y / 256.0 if y > 1.0 else y
                norm_w = w / 256.0 if w > 1.0 else w
                norm_h = h / 256.0 if h > 1.0 else h

                box = [
                    round(max(0.0, min(1.0, norm_y)), 3),
                    round(max(0.0, min(1.0, norm_x)), 3),
                    round(max(0.0, min(1.0, norm_y + norm_h)), 3),
                    round(max(0.0, min(1.0, norm_x + norm_w)), 3),
                ]
                saliency = float(b.get("saliency_score", b.get("relative_area", 0.85)))
                pathology = b.get("pathology", pathology_name)
            elif isinstance(b, (list, tuple)) and len(b) == 4:
                box = [round(float(coord), 3) for coord in b]
                saliency = 0.85
                pathology = pathology_name
            else:
                continue

            # Estimate anatomical region based on center coordinates
            center_y = (box[0] + box[2]) / 2.0
            center_x = (box[1] + box[3]) / 2.0

            if 0.30 <= center_x <= 0.70 and 0.35 <= center_y <= 0.75:
                anat_zone = "Cardiac Silhouette / Mediastinal Zone"
            elif center_y > 0.65 and center_x < 0.45:
                anat_zone = "Right Lower Lobe / Costophrenic Angle"
            elif center_y > 0.65 and center_x >= 0.45:
                anat_zone = "Left Lower Lobe / Costophrenic Angle"
            elif center_y < 0.35 and center_x < 0.50:
                anat_zone = "Right Upper Thoracic Apex"
            elif center_y < 0.35 and center_x >= 0.50:
                anat_zone = "Left Upper Thoracic Apex"
            elif center_x < 0.50:
                anat_zone = "Right Mid-Lung Field"
            else:
                anat_zone = "Left Mid-Lung Field"

            regions.append(
                AttentionRegion(
                    box=box,
                    saliency_score=round(min(1.0, max(0.0, saliency)), 3),
                    anatomical_region=anat_zone,
                    associated_pathology=pathology,
                )
            )

        return regions
