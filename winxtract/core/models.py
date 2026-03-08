from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class SourceConfig(BaseModel):
    slug: str
    name: str | None = None
    scraper: str
    start_urls: list[HttpUrl]
    selectors: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    respect_robots: bool = True
    enabled: bool = True


class RawRecord(BaseModel):
    source_slug: str
    page_url: str
    payload: dict[str, Any]


class LeadData(BaseModel):
    source_slug: str
    name: str | None = None
    city: str | None = None
    category: str | None = None
    website: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    description: str | None = None
    address: str | None = None
    page_url: str | None = None
    score: int = 0
    fingerprint: str
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScrapeStats(BaseModel):
    pages_scraped: int = 0
    leads_extracted: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
