from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from winxtract.core.models import LeadData
from winxtract.storage.db import ErrorLogORM, LeadORM, ScrapeJobORM, SourceORM


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_source(self, slug: str, scraper: str, enabled: bool = True) -> None:
        source = self.session.scalar(select(SourceORM).where(SourceORM.slug == slug))
        if source is None:
            source = SourceORM(slug=slug, scraper=scraper, enabled=enabled)
            self.session.add(source)
        else:
            source.scraper = scraper
            source.enabled = enabled
        self.session.commit()

    def create_job(self, source_slug: str) -> ScrapeJobORM:
        job = ScrapeJobORM(source_slug=source_slug, status="running")
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def finish_job(self, job_id: int, *, status: str, pages: int, leads: int, errors: int) -> None:
        job = self.session.get(ScrapeJobORM, job_id)
        if not job:
            return
        job.status = status
        job.pages_scraped = pages
        job.leads_extracted = leads
        job.errors = errors
        job.finished_at = datetime.now(timezone.utc)
        self.session.commit()

    def add_or_update_lead(self, lead: LeadData) -> bool:
        existing = self.session.scalar(select(LeadORM).where(LeadORM.fingerprint == lead.fingerprint))
        created = False
        if existing is None:
            existing = LeadORM(fingerprint=lead.fingerprint, source_slug=lead.source_slug)
            self.session.add(existing)
            created = True
        existing.name = lead.name
        existing.city = lead.city
        existing.category = lead.category
        existing.website = lead.website
        existing.emails = ",".join(lead.emails)
        existing.phones = ",".join(lead.phones)
        existing.description = lead.description
        existing.address = lead.address
        existing.page_url = lead.page_url
        existing.score = lead.score
        existing.scraped_at = lead.scraped_at
        self.session.commit()
        return created

    def log_error(self, source_slug: str, page_url: str | None, exc: Exception) -> None:
        row = ErrorLogORM(
            source_slug=source_slug,
            page_url=page_url,
            error_type=type(exc).__name__,
            message=str(exc),
        )
        self.session.add(row)
        self.session.commit()
