"""
MedFusion AI — Audit Log Repository.

Encapsulates database operations for immutable security and compliance audit trails:
- Append-only event logging
- Filtered compliance queries (by user, action, resource, timestamp range)
- Paginated retrieval for security auditors
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditAction, AuditResourceType
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository managing immutable audit trail logs."""

    def __init__(self, session: AsyncSession):
        super().__init__(AuditLog, session)

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
        """Create and persist an immutable compliance audit record."""
        entry = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def list_logs(
        self,
        user_id: Optional[UUID] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[AuditResourceType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Query audit trail records with multi-criteria compliance filtering."""
        stmt = select(AuditLog).options(selectinload(AuditLog.user))

        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if start_time is not None:
            stmt = stmt.where(AuditLog.timestamp >= start_time)
        if end_time is not None:
            stmt = stmt.where(AuditLog.timestamp <= end_time)

        stmt = stmt.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_logs(
        self,
        user_id: Optional[UUID] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[AuditResourceType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Count audit records matching the specified criteria."""
        stmt = select(func.count()).select_from(AuditLog)

        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if start_time is not None:
            stmt = stmt.where(AuditLog.timestamp >= start_time)
        if end_time is not None:
            stmt = stmt.where(AuditLog.timestamp <= end_time)

        result = await self.session.execute(stmt)
        return result.scalar() or 0
