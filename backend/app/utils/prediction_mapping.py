"""Translate persisted prediction records into the public API contract."""


from app.models.prediction_record import PredictionRecord, PredictionStatus
from app.schemas.prediction import (
    ExplainabilityDetail,
    ModalityGatingDetail,
    PathologyDetail,
    PredictionResponse,
    TabularRiskDetail,
    UncertaintyDetail,
)


def prediction_record_to_response(
    record: PredictionRecord,
    explanation_override: ExplainabilityDetail | None = None,
) -> PredictionResponse:
    """Map stored model output and its explanation into the API response."""
    detailed = record.detailed_predictions or {}
    pathology_findings = [
        PathologyDetail(**finding)
        for finding in detailed.get("pathology_findings", [])
    ]
    clinical_risk_data = detailed.get("clinical_risk")
    clinical_risk = (
        TabularRiskDetail(**clinical_risk_data) if clinical_risk_data else None
    )
    gating_data = detailed.get("modality_gating")
    modality_gating = ModalityGatingDetail(**gating_data) if gating_data else None

    uncertainty_data = detailed.get("uncertainty", {})
    uncertainty = UncertaintyDetail(
        entropy=uncertainty_data.get("entropy", 0.0),
        confidence_score=uncertainty_data.get(
            "confidence_score", record.confidence_score
        ),
        confidence_band=uncertainty_data.get(
            "confidence_band", record.confidence_band.value
        ),
        cross_modal_conflict=uncertainty_data.get("cross_modal_conflict"),
        abstention_recommended=uncertainty_data.get(
            "abstention_recommended",
            record.status == PredictionStatus.ABSTAINED,
        ),
        abstention_reasons=uncertainty_data.get(
            "abstention_reasons",
            [record.abstention_reason] if record.abstention_reason else [],
        ),
    )

    explanation = explanation_override
    if explanation is None and record.explanation is not None:
        explanation = ExplainabilityDetail(
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
        image_record_id=record.image_record_id,
        clinical_record_id=record.clinical_record_id,
        image_file_hash=record.image_file_hash,
        clinical_record_updated_at=record.clinical_record_updated_at,
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
        explanation=explanation,
        created_at=record.created_at,
    )
