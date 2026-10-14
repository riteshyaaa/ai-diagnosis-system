"""Owner-scoped report-preview API tests."""

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditAction, AuditLog
from app.models.clinical_record import ClinicalRecord
from app.models.prediction_record import (
    ConfidenceBand,
    ModelType,
    PredictionRecord,
    PredictionStatus,
)


async def register_clinician(client: AsyncClient, email: str) -> dict[str, str]:
    password = "ReportTestSecure2026!"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Report Test Clinician",
            "password": password,
        },
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def create_tabular_case(client: AsyncClient, headers: dict[str, str]) -> str:
    patient = await client.post(
        "/api/v1/patients",
        json={"mrn": "MRN-REPORT-TEST-01", "age": 59, "sex": "female"},
        headers=headers,
    )
    assert patient.status_code == 201
    case = await client.post(
        "/api/v1/cases",
        json={
            "patient_id": patient.json()["id"],
            "modality": "tabular_only",
            "clinical_notes": "Free text is intentionally excluded from the report preview.",
        },
        headers=headers,
    )
    assert case.status_code == 201
    return case.json()["id"]


def clinical_input_payload() -> dict[str, object]:
    return {
        "age": 59,
        "sex": 0,
        "chest_pain_type": 2,
        "resting_bp": 132,
        "cholesterol": 218,
        "fasting_bs": 0,
        "resting_ecg": 0,
        "max_hr": 151,
        "exercise_angina": 0,
        "st_depression": 0.2,
        "st_slope": 1,
        "num_major_vessels": 0,
        "thalassemia": 1,
    }


@pytest.mark.asyncio
async def test_report_preview_uses_persisted_inputs_without_direct_identifiers(
    client: AsyncClient,
    db_session: AsyncSession,
):
    headers = await register_clinician(client, "report.owner@hospital.org")
    case_id = await create_tabular_case(client, headers)
    input_response = await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=clinical_input_payload(),
        headers=headers,
    )
    assert input_response.status_code == 201

    response = await client.get(
        f"/api/v1/cases/{case_id}/report-preview", headers=headers
    )

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["status"] == "DRAFT"
    assert report["case_id"] == case_id
    assert report["patient"] == {"age": 59, "sex": "female"}
    assert report["clinical_input"]["resting_bp_mm_hg"] == 132
    assert report["clinical_input"]["id"] == input_response.json()["record"]["id"]
    assert report["prediction"] is None
    assert report["free_text_notes_included"] is False
    assert "mrn_hash" not in str(report)
    assert "clinical_notes" not in report
    assert "not a finalized report" in report["disclaimer"].lower()
    audit_events = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == AuditAction.CASE_VIEW,
            AuditLog.resource_id == case_id,
        )
    )
    assert any(
        event.details == {"view_type": "report_preview"}
        for event in audit_events.scalars().all()
    )


@pytest.mark.asyncio
async def test_report_preview_marks_current_model_output_pending_review(
    client: AsyncClient,
    db_session: AsyncSession,
):
    headers = await register_clinician(client, "report.prediction@hospital.org")
    case_id = await create_tabular_case(client, headers)
    input_response = await client.post(
        f"/api/v1/cases/{case_id}/clinical-records",
        json=clinical_input_payload(),
        headers=headers,
    )
    assert input_response.status_code == 201
    clinical_id = UUID(input_response.json()["record"]["id"])
    clinical_record = await db_session.get(ClinicalRecord, clinical_id)
    assert clinical_record is not None

    prediction = PredictionRecord(
        case_id=UUID(case_id),
        clinical_record_id=clinical_record.id,
        clinical_record_updated_at=clinical_record.updated_at,
        model_type=ModelType.TABULAR_MLP,
        model_version="1.0.0",
        primary_condition="model-reported risk finding",
        raw_probability=0.6,
        calibrated_probability=0.55,
        confidence_score=0.55,
        confidence_band=ConfidenceBand.LOW,
        status=PredictionStatus.UNCERTAIN,
        detailed_predictions={},
        inference_latency_ms=3.5,
    )
    db_session.add(prediction)
    await db_session.commit()
    await db_session.refresh(prediction)

    response = await client.get(
        f"/api/v1/cases/{case_id}/report-preview", headers=headers
    )

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["status"] == "PENDING_REVIEW"
    assert report["prediction"]["input_version_current"] is True
    assert (
        report["prediction"]["model_reported_finding"] == "model-reported risk finding"
    )
    assert "not verified as calibrated" in report["probability_notice"]
    assert report["review"] is None

    update_response = await client.patch(
        f"/api/v1/clinical-records/{clinical_id}",
        json={"resting_bp": 133},
        headers=headers,
    )
    assert update_response.status_code == 200, update_response.text
    stale_response = await client.get(
        f"/api/v1/cases/{case_id}/report-preview", headers=headers
    )

    assert stale_response.status_code == 200, stale_response.text
    assert stale_response.json()["status"] == "DRAFT"
    assert stale_response.json()["prediction"]["input_version_current"] is False


@pytest.mark.asyncio
async def test_report_preview_is_owner_scoped(client: AsyncClient):
    owner_headers = await register_clinician(
        client, "report.private.owner@hospital.org"
    )
    other_headers = await register_clinician(
        client, "report.private.other@hospital.org"
    )
    case_id = await create_tabular_case(client, owner_headers)

    response = await client.get(
        f"/api/v1/cases/{case_id}/report-preview", headers=other_headers
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_report_pdf_generation_and_audit(client: AsyncClient, db_session: AsyncSession):
    headers = await register_clinician(client, "report.pdf.owner@hospital.org")
    case_id = await create_tabular_case(client, headers)

    response = await client.get(f"/api/v1/cases/{case_id}/report-pdf", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

    audit_result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.resource_id == case_id,
            AuditLog.action == AuditAction.REPORT_EXPORT_PDF,
        )
    )
    event = audit_result.scalar_one_or_none()
    assert event is not None
    assert event.details["view_type"] == "report_pdf"
    assert event.details["pdf_size_bytes"] > 0


@pytest.mark.asyncio
async def test_report_pdf_is_owner_scoped(client: AsyncClient):
    owner_headers = await register_clinician(client, "report.pdf.private@hospital.org")
    other_headers = await register_clinician(client, "report.pdf.intruder@hospital.org")
    case_id = await create_tabular_case(client, owner_headers)

    response = await client.get(
        f"/api/v1/cases/{case_id}/report-pdf", headers=other_headers
    )
    assert response.status_code == 404

