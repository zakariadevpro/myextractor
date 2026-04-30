import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LeadEmailSchema(BaseModel):
    email: str
    is_valid: bool | None = None
    is_primary: bool = False

    model_config = {"from_attributes": True}


class LeadPhoneSchema(BaseModel):
    phone_raw: str | None = None
    phone_normalized: str | None = None
    phone_type: str = "unknown"
    is_valid: bool | None = None
    is_primary: bool = False

    model_config = {"from_attributes": True}


class LeadResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    extraction_job_id: uuid.UUID | None = None
    company_name: str
    siren: str | None = None
    naf_code: str | None = None
    sector: str | None = None
    website: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    department: str | None = None
    region: str | None = None
    quality_score: int = 0
    source: str
    source_url: str | None = None
    lead_kind: Literal["b2b", "b2c"] = "b2b"
    is_duplicate: bool = False
    is_similar: bool = False
    consent_status: Literal["granted", "denied", "revoked", "unknown"] = "unknown"
    emails: list[LeadEmailSchema] = []
    phones: list[LeadPhoneSchema] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadUpdate(BaseModel):
    company_name: str | None = None
    sector: str | None = None
    website: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None


class LeadFilters(BaseModel):
    min_score: int | None = None
    max_score: int | None = None
    extraction_job_id: uuid.UUID | None = None
    sector: str | None = None
    city: str | None = None
    department: str | None = None
    region: str | None = None
    source: str | None = None
    lead_kind: Literal["b2b", "b2c"] | None = None
    has_email: bool | None = None
    has_phone: bool | None = None
    is_duplicate: bool | None = None
    is_similar: bool | None = None
    consent_granted_only: bool | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search: str | None = None


class SuggestedSegment(BaseModel):
    code: str
    label: str
    description: str
    count: int
    filters: dict[str, str | int | bool]


class SuggestedSegmentResponse(BaseModel):
    items: list[SuggestedSegment]
