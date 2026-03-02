import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        *,
        action: str,
        organization_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        resource_type: str = "system",
        resource_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        log_entry = AuditLog(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        self.db.add(log_entry)

    async def list_logs(
        self,
        *,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        action: str | None = None,
        resource_type: str | None = None,
        actor_user_id: uuid.UUID | None = None,
    ) -> tuple[list[AuditLog], int]:
        offset = (page - 1) * page_size
        query = select(AuditLog).where(AuditLog.organization_id == organization_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if actor_user_id:
            query = query.where(AuditLog.actor_user_id == actor_user_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
        )
        return result.scalars().all(), total

    async def summary(self, *, organization_id: uuid.UUID, since_hours: int = 24) -> dict:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        base = select(AuditLog).where(
            AuditLog.organization_id == organization_id,
            AuditLog.created_at >= since,
        )
        total_q = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(total_q)).scalar() or 0

        actors_q = select(func.count(distinct(AuditLog.actor_user_id))).where(
            AuditLog.organization_id == organization_id,
            AuditLog.created_at >= since,
            AuditLog.actor_user_id.is_not(None),
        )
        unique_actors = (await self.db.execute(actors_q)).scalar() or 0

        action_q = (
            select(AuditLog.action, func.count().label("count"))
            .where(
                AuditLog.organization_id == organization_id,
                AuditLog.created_at >= since,
            )
            .group_by(AuditLog.action)
            .order_by(func.count().desc())
            .limit(20)
        )
        action_rows = (await self.db.execute(action_q)).all()
        return {
            "since_hours": since_hours,
            "total_events": total,
            "unique_actors": unique_actors,
            "events_by_action": [
                {"action": action_name, "count": int(action_count)}
                for action_name, action_count in action_rows
            ],
        }
