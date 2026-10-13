"""Database repository for application audit events.

Rows are persisted by this repository but are not protected against database-level
modification or deletion.
"""

from datetime import datetime
import math
import re
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditAction, AuditResourceType
from app.repositories.base import BaseRepository

_SAFE_ENUM_DETAILS = {
    "auth_method": {"password", "refresh_token"},
    "lookup_method": {"mrn_search"},
    "view_type": {"full_relational_graph", "report_preview"},
    "modality": {"image_only", "tabular_only", "multimodal"},
    "status": {
        "draft",
        "submitted",
        "processing",
        "completed",
        "reviewed",
        "archived",
        "confident",
        "uncertain",
        "abstained",
    },
    "initial_status": {"draft", "submitted", "processing", "completed", "reviewed", "archived"},
    "old_status": {"draft", "submitted", "processing", "completed", "reviewed", "archived"},
    "new_status": {"draft", "submitted", "processing", "completed", "reviewed", "archived"},
    "decision": {"accept", "modify", "reject"},
    "explanation_type": {"gradcam_saliency", "shap_feature_importance", "multimodal_attribution"},
    "model_type": {
        "image_densenet121",
        "image_efficientnet_b0",
        "vision_classifier",
        "tabular_mlp",
        "tabular_xgboost",
        "tabular_logistic_regression",
        "tabular_random_forest",
        "multimodal_fusion",
    },
}
_SAFE_NUMBER_DETAILS = {
    "latency_ms",
    "quality_score",
    "warnings_count",
    "features_count",
    "attention_regions_count",
}
_SAFE_BOOLEAN_DETAILS = {"mfa", "abstention_recommended"}
_SAFE_CASE_STATUSES = {"draft", "submitted", "processing", "completed", "reviewed", "archived"}


def _sanitize_details(details: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Keep only bounded technical metadata; discard clinical/user supplied values."""
    if not details:
        return None

    safe: Dict[str, Any] = {}
    for key, value in details.items():
        if not isinstance(key, str):
            continue
        normalized_key = key.strip().lower()

        if normalized_key in _SAFE_ENUM_DETAILS and isinstance(value, str):
            normalized_value = value.strip().lower()
            if normalized_value in _SAFE_ENUM_DETAILS[normalized_key]:
                safe[normalized_key] = normalized_value
        elif normalized_key == "model_version" and isinstance(value, str):
            version = value.strip()
            if re.fullmatch(r"v?\d+\.\d+\.\d+|[a-fA-F0-9]{7,64}", version):
                safe[normalized_key] = version
        elif normalized_key == "transition" and isinstance(value, str):
            match = re.fullmatch(r"\s*(\w+)\s*->\s*(\w+)\s*", value)
            if (
                match
                and match.group(1).lower() in _SAFE_CASE_STATUSES
                and match.group(2).lower() in _SAFE_CASE_STATUSES
            ):
                safe[normalized_key] = f"{match.group(1).lower()} -> {match.group(2).lower()}"
        elif normalized_key == "dimensions" and isinstance(value, str):
            if re.fullmatch(r"\d{1,5}x\d{1,5}", value):
                safe[normalized_key] = value
        elif (
            normalized_key in _SAFE_NUMBER_DETAILS
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            if value >= 0 and (not isinstance(value, float) or math.isfinite(value)):
                safe[normalized_key] = value
        elif normalized_key in _SAFE_BOOLEAN_DETAILS and isinstance(value, bool):
            safe[normalized_key] = value
        elif normalized_key == "updated_fields" and isinstance(value, list):
            safe["updated_field_count"] = len(value)

    return safe or None


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for persisted audit-event rows."""

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
        """Create and persist an audit-event row."""
        entry = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=_sanitize_details(details),
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
        """Query audit-event rows with multi-criteria filtering."""
        stmt = select(AuditLog)

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
