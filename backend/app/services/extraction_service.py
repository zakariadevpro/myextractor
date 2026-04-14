import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import ExtractionJob
from app.models.user import User
from app.schemas.extraction import ExtractionCreate

logger = logging.getLogger(__name__)


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
        if (data.first_name or "").strip() and (data.last_name or "").strip():
            add(f"{data.first_name.strip()} {data.last_name.strip()}")
        add(data.company_name)
        add(data.first_name)
        add(data.last_name)
        add(data.postal_code)
        add(data.department)
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

        # Store dispatch info — actual Celery send happens after commit via dispatch_job()
        self._pending_job_id = str(job.id)
        self._pending_target_kind = data.target_kind

        return job

    def dispatch_job(self):
        """Send the pending job to Celery. Must be called after DB commit."""
        try:
            from app.tasks.celery_app import celery_app

            celery_app.send_task(
                "workers.tasks.scrape_tasks.execute_scraping",
                args=[self._pending_job_id, self._pending_target_kind],
                queue="scraping",
            )
        except Exception as e:
            logger.error(
                "Failed to dispatch extraction job %s to Celery: %s",
                self._pending_job_id, e,
            )
            raise
