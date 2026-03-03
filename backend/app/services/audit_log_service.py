import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.extraction import ExtractionJob


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

        extraction_where = (
            ExtractionJob.organization_id == organization_id,
            ExtractionJob.created_at >= since,
        )
        total_jobs = (
            await self.db.execute(
                select(func.count()).where(*extraction_where)
            )
        ).scalar() or 0
        completed_jobs = (
            await self.db.execute(
                select(func.count()).where(
                    *extraction_where,
                    ExtractionJob.status == "completed",
                )
            )
        ).scalar() or 0
        failed_jobs = (
            await self.db.execute(
                select(func.count()).where(
                    *extraction_where,
                    ExtractionJob.status == "failed",
                )
            )
        ).scalar() or 0
        running_jobs = (
            await self.db.execute(
                select(func.count()).where(
                    *extraction_where,
                    ExtractionJob.status == "running",
                )
            )
        ).scalar() or 0
        avg_leads_found = (
            await self.db.execute(
                select(func.coalesce(func.avg(ExtractionJob.leads_found), 0.0)).where(
                    *extraction_where,
                    ExtractionJob.status == "completed",
                )
            )
        ).scalar() or 0.0
        avg_duration_seconds = (
            await self.db.execute(
                select(
                    func.coalesce(
                        func.avg(
                            func.extract(
                                "epoch",
                                ExtractionJob.completed_at - ExtractionJob.started_at,
                            )
                        ),
                        0.0,
                    )
                ).where(
                    *extraction_where,
                    ExtractionJob.completed_at.is_not(None),
                    ExtractionJob.started_at.is_not(None),
                )
            )
        ).scalar() or 0.0
        filtered_non_b2b_total = (
            await self.db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(COALESCE(NULLIF(details->>'filtered_non_b2b', '')::int, 0)), 0)
                    FROM audit_logs
                    WHERE organization_id = :org_id
                      AND action = 'extraction.analytics'
                      AND created_at >= :since
                    """
                ),
                {"org_id": organization_id, "since": since},
            )
        ).scalar() or 0

        success_rate = (float(completed_jobs) / float(total_jobs) * 100.0) if total_jobs else 0.0

        return {
            "since_hours": since_hours,
            "total_events": total,
            "unique_actors": unique_actors,
            "events_by_action": [
                {"action": action_name, "count": int(action_count)}
                for action_name, action_count in action_rows
            ],
            "extraction_metrics": {
                "total_jobs": int(total_jobs),
                "completed_jobs": int(completed_jobs),
                "failed_jobs": int(failed_jobs),
                "running_jobs": int(running_jobs),
                "success_rate_pct": round(success_rate, 2),
                "avg_leads_found": round(float(avg_leads_found), 2),
                "avg_duration_seconds": round(float(avg_duration_seconds), 2),
                "filtered_non_b2b_total": int(filtered_non_b2b_total),
            },
        }
