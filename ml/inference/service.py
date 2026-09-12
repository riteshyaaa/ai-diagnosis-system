"""
MedFusion AI — Unified Multimodal AI Inference Service.

Coordinates the end-to-end clinical inference pipeline:
- Ingestion & validation of DICOM/RGB chest radiographs and structured EHR tabular parameters
- Cryptographic SHA-256 patient identifier hashing ensuring strict privacy compliance
- Multi-modality routing (Vision-only, Tabular-only, and Multimodal Late Fusion)
- Calibrated probability estimation and cardiovascular clinical risk tiering
- XAI generation: Grad-CAM thoracic localization heatmaps and SHAP clinical feature attributions
- Clinical safety abstention engine detecting low-confidence, borderline, and cross-modal conflicting cases
- Mandatory non-autonomous Clinical Decision Support System (CDSS) regulatory disclaimers
"""

import base64
import hashlib
import io
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image
import torch

from ml.config import ImageModelConfig, TabularModelConfig
from ml.datasets.chest_xray.quality_validator import ImageQualityValidator
from ml.datasets.chest_xray.transforms import MedicalImageTransforms
from ml.datasets.heart_disease.constants import CORE_FEATURE_NAMES
from ml.datasets.heart_disease.preprocessor import HeartDiseasePreprocessor
from ml.datasets.heart_disease.validator import ClinicalFeatureValidator
from ml.explainability.explain import GradCAMExplainer, SHAPExplainerEngine
from ml.inference.schemas import (
    ConfidenceBand,
    ExplainabilitySummary,
    InferenceModality,
    InferenceRequest,
    InferenceResponse,
    ModalityGatingWeights,
    PathologyFinding,
    RiskTier,
    TabularRiskFinding,
    UncertaintyEstimation,
)
from ml.registry.registry import ModelRegistry, ModelType

logger = logging.getLogger(__name__)

TARGET_PATHOLOGIES = [
    "Atelectasis",
    "Cardiomegaly",
    "Effusion",
    "Infiltration",
    "Mass",
]


class UnifiedInferenceService:
    """
    Production-grade Unified Inference Engine for MedFusion AI.
    Handles multimodal diagnosis, uncertainty estimation, and auditable explainability.
    """

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        device: Optional[str] = None,
    ):
        self.device = torch.device(
            device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.registry = registry or ModelRegistry()
        self.registry.ensure_default_models_registered()

        self.image_transforms = MedicalImageTransforms()
        self.tabular_preprocessor = HeartDiseasePreprocessor()

        # Cached models
        self._vision_model = None
        self._tabular_model = None
        self._fusion_model = None
        self._tabular_calibrator = None

        self._load_active_models()

    def _load_active_models(self) -> None:
        """Load default active models from registry into memory."""
        try:
            v_model, _, _ = self.registry.load_model("chest_xray_vision", map_location=str(self.device))
            self._vision_model = v_model.to(self.device).eval()
        except Exception as e:
            logger.warning("Failed to load active chest_xray_vision model: %s", e)

        try:
            t_model, _, t_aux = self.registry.load_model("tabular_risk_mlp", map_location=str(self.device))
            self._tabular_model = t_model.to(self.device).eval()
            self._tabular_calibrator = t_aux.get("calibrator")
        except Exception as e:
            logger.warning("Failed to load active tabular_risk_mlp model: %s", e)

        try:
            f_model, _, _ = self.registry.load_model("multimodal_late_fusion", map_location=str(self.device))
            self._fusion_model = f_model.to(self.device).eval()
        except Exception as e:
            logger.warning("Failed to load active multimodal_late_fusion model: %s", e)

    @staticmethod
    def hash_patient_mrn(mrn: Optional[str]) -> Optional[str]:
        """Cryptographically hash patient Medical Record Number (MRN) with SHA-256."""
        if not mrn or not mrn.strip():
            return None
        return hashlib.sha256(mrn.strip().encode("utf-8")).hexdigest()

    def _preprocess_image(
        self,
        image_input: Union[str, Path, bytes, np.ndarray, Image.Image],
    ) -> Tuple[torch.Tensor, np.ndarray, List[str]]:
        """
        Validate, normalize, and convert input image into standardized RGB array and PyTorch tensor.
        Returns: (tensor [1, 3, 224, 224], raw_rgb_np [H, W, 3], quality_issues)
        """
        rgb_image: np.ndarray

        if isinstance(image_input, (str, Path)):
            path_obj = Path(image_input)
            if not path_obj.exists():
                raise FileNotFoundError(f"Image path not found: {image_input}")
            # Check if DICOM
            if path_obj.suffix.lower() in [".dcm", ".dicom"]:
                from ml.datasets.chest_xray.dicom_parser import DICOMParser
                parsed = DICOMParser.parse_dicom(path_obj)
                rgb_image = parsed.image_array
            else:
                bgr = cv2.imread(str(path_obj))
                if bgr is None:
                    raise ValueError(f"Unable to decode image file: {image_input}")
                rgb_image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        elif isinstance(image_input, bytes):
            # Try DICOM first, fallback to standard image
            if image_input.startswith(b"\x00" * 128 + b"DICM") or b"DICM" in image_input[:132]:
                from ml.datasets.chest_xray.dicom_parser import DICOMParser
                parsed = DICOMParser.parse_dicom(image_input)
                rgb_image = parsed.image_array
            else:
                nparr = np.frombuffer(image_input, np.uint8)
                bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if bgr is None:
                    # Try PIL fallback
                    pil_img = Image.open(io.BytesIO(image_input)).convert("RGB")
                    rgb_image = np.array(pil_img)
                else:
                    rgb_image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        elif isinstance(image_input, Image.Image):
            rgb_image = np.array(image_input.convert("RGB"))

        elif isinstance(image_input, np.ndarray):
            if image_input.ndim == 2:
                rgb_image = cv2.cvtColor(image_input, cv2.COLOR_GRAY2RGB)
            elif image_input.ndim == 3 and image_input.shape[2] == 3:
                rgb_image = image_input
            elif image_input.ndim == 3 and image_input.shape[2] == 4:
                rgb_image = cv2.cvtColor(image_input, cv2.COLOR_RGBA2RGB)
            else:
                raise ValueError(f"Invalid image array shape: {image_input.shape}")
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

        # Validate image quality
        quality_report = ImageQualityValidator.validate_image(rgb_image)
        issues = list(quality_report.issues)

        # Standardize transform for neural network ingestion [1, 3, 224, 224]
        tensor = self.image_transforms.eval_transforms(rgb_image).unsqueeze(0).to(self.device)

        return tensor, rgb_image, issues

    def _preprocess_tabular(
        self,
        tabular_data: Dict[str, Any],
    ) -> Tuple[torch.Tensor, np.ndarray, List[str]]:
        """
        Validate and preprocess structured EHR tabular telemetry into normalized tensor and array.
        Returns: (tensor [1, 13], feature_array [1, 13], validation_warnings)
        """
        report = ClinicalFeatureValidator.validate(tabular_data)
        if not report.is_valid:
            error_msg = "; ".join(report.errors)
            raise ValueError(f"Clinical tabular validation failed: {error_msg}")

        # Standardize features
        feature_vec = self.tabular_preprocessor.transform_dict(
            report.sanitized_features,
            normalize_continuous=True,
        )
        feature_array = feature_vec.reshape(1, -1)
        tensor = torch.from_numpy(feature_array).float().to(self.device)

        return tensor, feature_array, report.warnings

    @staticmethod
    def _compute_entropy(probs: List[float]) -> float:
        """Compute normalized binary predictive entropy across a sequence of probabilities."""
        if not probs:
            return 0.0
        entropies = []
        for p in probs:
            p_clamped = max(1e-6, min(1.0 - 1e-6, p))
            e = -(p_clamped * math.log2(p_clamped) + (1.0 - p_clamped) * math.log2(1.0 - p_clamped))
            entropies.append(e)
        return float(np.mean(entropies))

    @staticmethod
    def _determine_confidence_band(confidence_score: float) -> ConfidenceBand:
        """Categorize confidence score into standardized bands."""
        if confidence_score >= 0.85:
            return ConfidenceBand.HIGH
        elif confidence_score >= 0.60:
            return ConfidenceBand.MODERATE
        elif confidence_score >= 0.40:
            return ConfidenceBand.LOW
        else:
            return ConfidenceBand.ABSTAIN

    @staticmethod
    def _determine_risk_tier(probability: float) -> RiskTier:
        """Stratify cardiovascular clinical risk probability into clinical tiers."""
        if probability < 0.20:
            return RiskTier.LOW
        elif probability < 0.50:
            return RiskTier.MODERATE
        elif probability < 0.80:
            return RiskTier.HIGH
        else:
            return RiskTier.CRITICAL

    def _generate_gradcam_artifacts(
        self,
        model: Any,
        image_tensor: torch.Tensor,
        raw_rgb: np.ndarray,
        pathology_idx: int = 1,  # Default to Cardiomegaly
    ) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Compute Grad-CAM heatmap, generate visual overlay, and detect bounding box proposals.
        """
        try:
            explainer = GradCAMExplainer(model=model, device=str(self.device))
            cam = explainer.generate_heatmap(image_tensor, class_idx=pathology_idx, use_positive_only=True)

            # Resize heatmap to match original image dimensions
            h, w, _ = raw_rgb.shape
            heatmap_resized = cv2.resize(cam, (w, h))

            # Generate colored heatmap
            heatmap_uint8 = np.uint8(255 * heatmap_resized)
            colormap = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
            colormap_rgb = cv2.cvtColor(colormap, cv2.COLOR_BGR2RGB)

            # Blend with raw image (40% heatmap, 60% radiograph)
            overlay = np.uint8(0.6 * raw_rgb + 0.4 * colormap_rgb)

            # Detect bounding boxes above 60% activation threshold
            threshold_val = int(255 * 0.60)
            _, thresh_img = cv2.threshold(heatmap_uint8, threshold_val, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            bounding_boxes = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > (h * w * 0.01):  # Filter out tiny noise spots (<1% area)
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    bounding_boxes.append({
                        "x": int(bx),
                        "y": int(by),
                        "width": int(bw),
                        "height": int(bh),
                        "relative_area": round(float(area / (h * w)), 4),
                        "pathology": TARGET_PATHOLOGIES[pathology_idx] if pathology_idx < len(TARGET_PATHOLOGIES) else "Pathology",
                    })

            # Encode images to Base64
            _, buffer_hm = cv2.imencode(".png", cv2.cvtColor(colormap_rgb, cv2.COLOR_RGB2BGR))
            base64_heatmap = base64.b64encode(buffer_hm).decode("utf-8")

            _, buffer_ov = cv2.imencode(".png", cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
            base64_overlay = base64.b64encode(buffer_ov).decode("utf-8")

            return base64_heatmap, base64_overlay, bounding_boxes
        except Exception as e:
            logger.warning("Grad-CAM generation failed: %s", e)
            return "", "", []

    def _generate_shap_artifacts(
        self,
        tabular_array: np.ndarray,
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Compute SHAP feature attributions for tabular clinical inputs.
        """
        try:
            explainer_engine = SHAPExplainerEngine(model=self._tabular_model)
            shap_res = explainer_engine.explain(
                X=tabular_array,
                feature_names=CORE_FEATURE_NAMES,
                n_samples=25,
            )
            top_features = []
            feat_dict = shap_res.get("feature_importance", {})
            for name, val in feat_dict.items():
                top_features.append({"feature": name, "attribution": float(val)})

            base_val = float(shap_res.get("base_value", 0.5))
            return top_features, base_val
        except Exception as e:
            logger.warning("SHAP generation failed: %s", e)
            return [], 0.5

    def explain_pathology(
        self,
        image_input: Union[str, Path, bytes, np.ndarray, Image.Image],
        target_pathology: str = "Cardiomegaly",
        target_layer: Optional[str] = None,
    ) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        On-demand Grad-CAM explainability recalculation for a specified thoracic pathology.
        Returns: (base64_heatmap, base64_overlay, bounding_boxes)
        """
        if target_pathology not in TARGET_PATHOLOGIES:
            raise ValueError(
                f"Unknown target pathology '{target_pathology}'. "
                f"Supported pathologies are: {TARGET_PATHOLOGIES}"
            )
        pathology_idx = TARGET_PATHOLOGIES.index(target_pathology)

        if self._vision_model is None:
            self._load_active_models()

        if self._vision_model is None:
            raise RuntimeError("Vision model not available for Grad-CAM explainability.")

        image_tensor, raw_rgb, _ = self._preprocess_image(image_input)
        return self._generate_gradcam_artifacts(
            model=self._vision_model,
            image_tensor=image_tensor,
            raw_rgb=raw_rgb,
            pathology_idx=pathology_idx,
        )

    def predict(
        self,
        request: InferenceRequest,
    ) -> InferenceResponse:
        """
        Execute full unified clinical inference on multimodal request.
        """
        has_image = (request.image_path is not None) or (request.image_bytes is not None)
        has_tabular = (request.tabular_features is not None) and len(request.tabular_features) > 0

        if not has_image and not has_tabular:
            raise ValueError("Inference request must provide either image data, tabular features, or both.")

        mrn_hash = self.hash_patient_mrn(request.patient_mrn)
        timestamp = datetime.utcnow().isoformat()

        # Modality selection
        if has_image and has_tabular:
            modality = InferenceModality.MULTIMODAL
        elif has_image:
            modality = InferenceModality.IMAGE_ONLY
        else:
            modality = InferenceModality.TABULAR_ONLY

        image_tensor = None
        raw_rgb = None
        img_issues = []
        if has_image:
            img_input = request.image_bytes if request.image_bytes is not None else request.image_path
            image_tensor, raw_rgb, img_issues = self._preprocess_image(img_input)

        tabular_tensor = None
        tabular_array = None
        tab_warnings = []
        if has_tabular:
            tabular_tensor, tabular_array, tab_warnings = self._preprocess_tabular(request.tabular_features)

        # Execute models
        pathology_probs_list: List[float] = []
        pathology_findings: List[PathologyFinding] = []
        clinical_risk: Optional[TabularRiskFinding] = None
        modality_gating: Optional[ModalityGatingWeights] = None
        model_meta: Dict[str, Any] = {"modality": modality.value}

        abstention_reasons: List[str] = []
        if img_issues:
            abstention_reasons.extend([f"Image quality issue: {iss}" for iss in img_issues])

        # --- MULTIMODAL INFERENCE ---
        if modality == InferenceModality.MULTIMODAL:
            if self._fusion_model is None:
                raise RuntimeError("Multimodal fusion model not loaded in registry.")

            with torch.no_grad():
                out = self._fusion_model(
                    image_input=image_tensor,
                    tabular_input=tabular_tensor,
                )

            # Pathologies
            path_probs = out["pathology_probs"].cpu().numpy().ravel()
            pathology_probs_list = path_probs.tolist()

            for idx, name in enumerate(TARGET_PATHOLOGIES):
                p = float(path_probs[idx])
                conf = self._determine_confidence_band(1.0 - 2.0 * abs(p - 0.5))
                pathology_findings.append(
                    PathologyFinding(
                        pathology=name,
                        probability=round(p, 4),
                        threshold=0.5,
                        positive=p >= 0.5,
                        confidence_band=conf,
                        calibrated_probability=round(p, 4),
                    )
                )

            # Clinical Risk
            raw_risk = float(out["risk_probs"].cpu().numpy().ravel()[0])
            calibrated_risk = raw_risk
            if self._tabular_calibrator is not None:
                calibrated_risk = float(self._tabular_calibrator.predict_proba(np.array([raw_risk]))[0])

            risk_conf = self._determine_confidence_band(1.0 - 2.0 * abs(calibrated_risk - 0.5))
            clinical_risk = TabularRiskFinding(
                raw_probability=round(raw_risk, 4),
                calibrated_probability=round(calibrated_risk, 4),
                risk_tier=self._determine_risk_tier(calibrated_risk),
                confidence_band=risk_conf,
                positive=calibrated_risk >= 0.5,
            )

            # Modality Gating
            if "modality_gates" in out:
                gates = out["modality_gates"].cpu().numpy().ravel()
                img_w = float(gates[0])
                tab_w = float(gates[1])
            else:
                img_w, tab_w = 0.5, 0.5

            dominant = "Radiograph Visual Features" if img_w >= tab_w else "EHR Tabular Risk Parameters"
            modality_gating = ModalityGatingWeights(
                image_weight=round(img_w, 4),
                tabular_weight=round(tab_w, 4),
                dominant_modality=dominant,
            )
            model_meta["fusion_strategy"] = getattr(self._fusion_model, "fusion_strategy", "gated")

        # --- IMAGE ONLY INFERENCE ---
        elif modality == InferenceModality.IMAGE_ONLY:
            if self._vision_model is None:
                raise RuntimeError("Chest X-Ray vision model not loaded in registry.")

            with torch.no_grad():
                out = self._vision_model(image_tensor)
                path_probs = out["probabilities"].cpu().numpy().ravel()
                pathology_probs_list = path_probs.tolist()

            for idx, name in enumerate(TARGET_PATHOLOGIES):
                p = float(path_probs[idx])
                conf = self._determine_confidence_band(1.0 - 2.0 * abs(p - 0.5))
                pathology_findings.append(
                    PathologyFinding(
                        pathology=name,
                        probability=round(p, 4),
                        threshold=0.5,
                        positive=p >= 0.5,
                        confidence_band=conf,
                        calibrated_probability=round(p, 4),
                    )
                )
            model_meta["backbone"] = getattr(self._vision_model, "backbone_name", "densenet121")

        # --- TABULAR ONLY INFERENCE ---
        elif modality == InferenceModality.TABULAR_ONLY:
            if self._tabular_model is None:
                raise RuntimeError("Tabular risk model not loaded in registry.")

            with torch.no_grad():
                out = self._tabular_model(tabular_tensor)
                raw_risk = float(out["probabilities"].cpu().numpy().ravel()[0])

            calibrated_risk = raw_risk
            if self._tabular_calibrator is not None:
                calibrated_risk = float(self._tabular_calibrator.predict_proba(np.array([raw_risk]))[0])

            risk_conf = self._determine_confidence_band(1.0 - 2.0 * abs(calibrated_risk - 0.5))
            clinical_risk = TabularRiskFinding(
                raw_probability=round(raw_risk, 4),
                calibrated_probability=round(calibrated_risk, 4),
                risk_tier=self._determine_risk_tier(calibrated_risk),
                confidence_band=risk_conf,
                positive=calibrated_risk >= 0.5,
            )
            model_meta["model_architecture"] = "TabularRiskMLP"

        # --- UNCERTAINTY ESTIMATION & CROSS-MODAL CONFLICT ---
        all_eval_probs = list(pathology_probs_list)
        if clinical_risk is not None:
            all_eval_probs.append(clinical_risk.calibrated_probability)

        entropy = self._compute_entropy(all_eval_probs)
        confidence_score = round(max(0.0, min(1.0, 1.0 - entropy)), 4)
        overall_conf_band = self._determine_confidence_band(confidence_score)

        cross_modal_conflict = None
        if modality == InferenceModality.MULTIMODAL and len(pathology_findings) > 1 and clinical_risk is not None:
            # Check cardiomegaly vs cardiovascular risk dissonance
            cardiomegaly_prob = next((f.probability for f in pathology_findings if f.pathology == "Cardiomegaly"), 0.0)
            risk_prob = clinical_risk.calibrated_probability
            conflict = abs(cardiomegaly_prob - risk_prob)
            cross_modal_conflict = round(conflict, 4)

            if conflict >= 0.55:
                abstention_reasons.append(
                    f"High cross-modal discordance detected: Cardiomegaly prob ({cardiomegaly_prob:.2f}) "
                    f"vs Tabular Risk prob ({risk_prob:.2f})."
                )

        # Borderline risk check
        if clinical_risk is not None and 0.45 <= clinical_risk.calibrated_probability <= 0.55:
            abstention_reasons.append(
                f"Borderline clinical risk score ({clinical_risk.calibrated_probability:.3f}) requires physician review."
            )

        # Low confidence check
        if confidence_score < 0.55:
            abstention_reasons.append(
                f"Predictive confidence ({confidence_score:.2f}) is below safe threshold (0.55)."
            )

        abstention_recommended = len(abstention_reasons) > 0
        if abstention_recommended:
            overall_conf_band = ConfidenceBand.ABSTAIN

        uncertainty = UncertaintyEstimation(
            entropy=round(entropy, 4),
            confidence_score=confidence_score,
            confidence_band=overall_conf_band,
            cross_modal_conflict=cross_modal_conflict,
            abstention_recommended=abstention_recommended,
            abstention_reasons=abstention_reasons,
        )

        # --- EXPLAINABILITY ARTIFACTS ---
        explainability = None
        if request.generate_explainability:
            gradcam_hm = None
            gradcam_ov = None
            bboxes = None
            shap_contribs = None
            shap_base = None

            if has_image and raw_rgb is not None:
                # Target highest confidence or positive pathology
                target_idx = 1  # Cardiomegaly
                if pathology_probs_list:
                    target_idx = int(np.argmax(pathology_probs_list))

                model_for_cam = self._vision_model
                if modality == InferenceModality.MULTIMODAL and hasattr(self._fusion_model, "image_model"):
                    model_for_cam = self._fusion_model.image_model

                if model_for_cam is not None:
                    gradcam_hm, gradcam_ov, bboxes = self._generate_gradcam_artifacts(
                        model=model_for_cam,
                        image_tensor=image_tensor,
                        raw_rgb=raw_rgb,
                        pathology_idx=target_idx,
                    )

            if has_tabular and tabular_array is not None:
                shap_contribs, shap_base = self._generate_shap_artifacts(tabular_array)

            explainability = ExplainabilitySummary(
                gradcam_heatmap_base64=gradcam_hm,
                gradcam_overlay_base64=gradcam_ov,
                gradcam_bounding_boxes=bboxes,
                shap_feature_contributions=shap_contribs,
                shap_base_value=shap_base,
            )

        return InferenceResponse(
            timestamp=timestamp,
            modality=modality,
            patient_mrn_hash=mrn_hash,
            pathology_findings=pathology_findings,
            clinical_risk=clinical_risk,
            modality_gating=modality_gating,
            uncertainty=uncertainty,
            explainability=explainability,
            model_metadata=model_meta,
        )
