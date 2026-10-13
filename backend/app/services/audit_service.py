"""Service for writing and querying application audit events.

The audit table is an ordinary mutable database table and does not by itself
provide tamper-evidence, immutability, or regulatory compliance.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditAction, AuditResourceType
from app.repositories.audit_log_repository import AuditLogRepository


class AuditService:
    """Service for creating and querying application audit events."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AuditLogRepository(session)

    async def log_event(
        self,
        action: AuditAction,
        resource_type: AuditResourceType,
        resource_id: Optional[str] = None,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Record an application event in the audit table.
        """
        return await self.repository.log_event(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )

    async def get_audit_trail(
        self,
        user_id: Optional[UUID] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[AuditResourceType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Retrieve paginated audit events matching query filters.
        """
        return await self.repository.list_logs(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            start_time=start_time,
            end_time=end_time,
            skip=skip,
            limit=limit,
        )

    async def count_audit_trail(
        self,
        user_id: Optional[UUID] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[AuditResourceType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        Count audit events matching query filters.
        """
        return await self.repository.count_logs(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            start_time=start_time,
            end_time=end_time,
        )
