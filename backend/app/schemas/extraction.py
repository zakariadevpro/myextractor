import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ALLOWED_B2B_SOURCES = {"google_maps", "pages_jaunes", "sirene_api", "whiteextractor"}


class ExtractionCreate(BaseModel):
    source: str = "whiteextractor"
    keywords: list[str] = Field(..., min_length=1)
    city: str | None = None
    postal_code: str | None = None
    radius_km: int | None = Field(None, ge=1, le=100)
    sector_filter: str | None = None
    max_leads: int = Field(100, ge=1, le=1000)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str):
        if value not in ALLOWED_B2B_SOURCES:
            allowed = ", ".join(sorted(ALLOWED_B2B_SOURCES))
            raise ValueError(f"Unsupported source '{value}'. Allowed: {allowed}")
        return value


class ExtractionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    source: str
    keywords: list[str] | None
    city: str | None
    postal_code: str | None
    radius_km: int | None
    sector_filter: str | None
    max_leads: int
    status: str
    progress: int
    leads_found: int
    leads_new: int
    leads_duplicate: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
