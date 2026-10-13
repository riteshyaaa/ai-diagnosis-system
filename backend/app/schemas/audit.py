"""Response schemas for read-only audit-event queries."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.audit_log import AuditAction, AuditResourceType


class AuditEventResponse(BaseModel):
    """Minimal event fields; free-form details and network metadata are omitted."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: Optional[UUID] = None
    action: AuditAction
    resource_type: AuditResourceType
    resource_id: Optional[str] = None
    timestamp: datetime


class AuditEventListResponse(BaseModel):
    """One page of audit events and pagination metadata."""

    total: int
    skip: int
    limit: int
    items: List[AuditEventResponse]
