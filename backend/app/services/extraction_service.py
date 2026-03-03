from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import ExtractionJob
from app.models.user import User
from app.schemas.extraction import ExtractionCreate


class ExtractionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _build_keywords(data: ExtractionCreate) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()

        def add(value: str | None):
            cleaned = (value or "").strip()
            if not cleaned:
                return
            key = cleaned.casefold()
            if key in seen:
                return
            seen.add(key)
            tokens.append(cleaned)

        for keyword in data.keywords or []:
            add(keyword)
        add(data.company_name)
        add(data.first_name)
        add(data.last_name)
        add(data.department)
        if data.target_kind == "b2c":
            add("particulier")
        if data.target_kind == "b2b":
            add("entreprise")
        return tokens

    async def create_job(self, data: ExtractionCreate, user: User) -> ExtractionJob:
        keywords = self._build_keywords(data)
        job = ExtractionJob(
            organization_id=user.organization_id,
            created_by=user.id,
            source=data.source,
            keywords=keywords,
            city=data.city,
            postal_code=data.postal_code,
            radius_km=data.radius_km,
            sector_filter=data.sector_filter,
            max_leads=data.max_leads,
            status="pending",
        )
        self.db.add(job)
        await self.db.flush()

        # Dispatch to Celery worker
        try:
            from app.tasks.celery_app import celery_app

            celery_app.send_task(
                "workers.tasks.scrape_tasks.execute_scraping",
                args=[str(job.id), data.target_kind],
                queue="scraping",
            )
        except Exception:
            # If Celery is not available, mark as failed
            job.status = "failed"
            job.error_message = "Task queue unavailable"
            await self.db.flush()

        return job
