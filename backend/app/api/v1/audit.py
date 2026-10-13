"""Read-only audit-event endpoints for administrators and auditors."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import ValidationError
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.user import User
from app.schemas.audit import AuditEventListResponse, AuditEventResponse
from app.security.dependencies import require_auditor
from app.services.audit_service import AuditService

router = APIRouter(tags=["Audit Events"])


@router.get(
    "/audit-events",
    response_model=AuditEventListResponse,
    summary="List Audit Events",
    description=(
        "List recorded audit events for administrator/auditor accounts. The response omits "
        "free-form event details, IP addresses, and user-agent strings. Audit rows are not "
        "guaranteed immutable or tamper-evident."
    ),
)
async def list_audit_events(
    current_user: User = Depends(require_auditor),
    session: AsyncSession = Depends(get_db),
    actor_id: Optional[UUID] = Query(None, description="Filter by event actor UUID"),
    action: Optional[AuditAction] = Query(None),
    resource_type: Optional[AuditResourceType] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
) -> AuditEventListResponse:
    """Return minimal audit-event metadata to authorized roles only."""
    if start_time and end_time and start_time > end_time:
        raise ValidationError("start_time must be earlier than or equal to end_time.")

    service = AuditService(session)
    filters = {
        "user_id": actor_id,
        "action": action,
        "resource_type": resource_type,
        "start_time": start_time,
        "end_time": end_time,
    }
    items = await service.get_audit_trail(**filters, skip=skip, limit=limit)
    total = await service.count_audit_trail(**filters)

    return AuditEventListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=[AuditEventResponse.model_validate(item) for item in items],
    )
