import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_B2B_SOURCES = {"google_maps", "pages_jaunes", "sirene_api", "whiteextractor"}
ALLOWED_TARGET_KINDS = {"b2b", "b2c", "both"}


class ExtractionCreate(BaseModel):
    source: str = "whiteextractor"
    target_kind: str = "both"
    keywords: list[str] = Field(default_factory=list)
    company_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    city: str | None = None
    postal_code: str | None = None
    department: str | None = None
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

    @field_validator("target_kind")
    @classmethod
    def validate_target_kind(cls, value: str):
        if value not in ALLOWED_TARGET_KINDS:
            allowed = ", ".join(sorted(ALLOWED_TARGET_KINDS))
            raise ValueError(f"Unsupported target_kind '{value}'. Allowed: {allowed}")
        return value

    @model_validator(mode="after")
    def validate_query_payload(self):
        has_keywords = any(str(item).strip() for item in self.keywords or [])
        has_company = bool((self.company_name or "").strip())
        has_person = bool((self.first_name or "").strip() or (self.last_name or "").strip())
        if self.target_kind == "b2b" and not (has_company or has_keywords):
            raise ValueError("B2B requires company_name or keywords.")
        if self.target_kind == "b2c" and not (has_person or has_keywords):
            raise ValueError("B2C requires first_name/last_name or keywords.")
        if self.target_kind == "both" and not (has_company or has_person or has_keywords):
            raise ValueError("Provide at least one of company_name, first_name, last_name or keywords.")
        return self


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
