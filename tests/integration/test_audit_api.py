"""Authorization and data-minimization tests for the audit-events API."""

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditAction, AuditLog, AuditResourceType
from app.models.user import UserRole
from tests.auth_support import login_as_provisioned_role


@pytest.mark.asyncio
async def test_audit_event_list_is_role_restricted_and_minimal(
    client: AsyncClient,
    db_session: AsyncSession,
):
    auditor_token = await login_as_provisioned_role(
        client,
        db_session,
        role=UserRole.AUDITOR,
        email="audit.reader@hospital.org",
        full_name="Audit Reader",
    )
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}
    identity = await client.get("/api/v1/auth/me", headers=auditor_headers)
    assert identity.status_code == 200

    db_session.add(
        AuditLog(
            user_id=UUID(identity.json()["id"]),
            action=AuditAction.CASE_CREATE,
            resource_type=AuditResourceType.CASE,
            resource_id="case-reference-1",
            details={"private_note": "must not be included in audit response"},
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/audit-events",
        params={"action": "case_create", "limit": 1},
        headers=auditor_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 1
    assert len(payload["items"]) == 1
    event = payload["items"][0]
    assert event["action"] == "case_create"
    assert event["resource_type"] == "case"
    assert event["resource_id"] == "case-reference-1"
    assert event["user_id"] == identity.json()["id"]
    assert "details" not in event
    assert "ip_address" not in event
    assert "user_agent" not in event

    admin_token = await login_as_provisioned_role(
        client,
        db_session,
        role=UserRole.ADMIN,
        email="audit.admin@hospital.org",
        full_name="Audit Administrator",
    )
    admin_response = await client.get(
        "/api/v1/audit-events?limit=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_response.status_code == 200

    clinician_token = await login_as_provisioned_role(
        client,
        db_session,
        role=UserRole.CLINICIAN,
        email="audit.clinician@hospital.org",
        full_name="Clinical User",
    )
    forbidden = await client.get(
        "/api/v1/audit-events",
        headers={"Authorization": f"Bearer {clinician_token}"},
    )
    assert forbidden.status_code == 403

    unauthenticated = await client.get("/api/v1/audit-events")
    assert unauthenticated.status_code == 401


@pytest.mark.asyncio
async def test_audit_event_time_filter_range_is_validated(client: AsyncClient, db_session: AsyncSession):
    auditor_token = await login_as_provisioned_role(
        client,
        db_session,
        role=UserRole.AUDITOR,
        email="audit.range@hospital.org",
        full_name="Audit Range Reader",
    )
    response = await client.get(
        "/api/v1/audit-events",
        params={"start_time": "2026-10-02T00:00:00Z", "end_time": "2026-10-01T00:00:00Z"},
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert response.status_code == 422
    assert "start_time" in response.json()["detail"].lower()
