import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ConsentStatus = Literal["granted", "denied", "revoked", "unknown"]
ConsentScope = Literal["email", "phone", "sms", "whatsapp", "all"]
LawfulBasis = Literal["consent", "contract", "legitimate_interest"]


class LeadConsentResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    organization_id: uuid.UUID
    consent_status: ConsentStatus
    consent_scope: ConsentScope
    consent_source: str | None = None
    consent_at: datetime | None = None
    consent_text_version: str | None = None
    consent_proof_ref: str | None = None
    privacy_policy_version: str | None = None
    lawful_basis: LawfulBasis
    source_campaign: str | None = None
    source_channel: str | None = None
    ip_hash: str | None = None
    user_agent_hash: str | None = None
    double_opt_in: bool
    double_opt_in_at: datetime | None = None
    purpose: str | None = None
    data_retention_until: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadConsentUpdate(BaseModel):
    consent_status: ConsentStatus | None = None
    consent_scope: ConsentScope | None = None
    consent_source: str | None = Field(default=None, max_length=50)
    consent_at: datetime | None = None
    consent_text_version: str | None = Field(default=None, max_length=50)
    consent_proof_ref: str | None = Field(default=None, max_length=255)
    privacy_policy_version: str | None = Field(default=None, max_length=50)
    lawful_basis: LawfulBasis | None = None
    source_campaign: str | None = Field(default=None, max_length=255)
    source_channel: str | None = Field(default=None, max_length=50)
    ip_hash: str | None = Field(default=None, max_length=128)
    user_agent_hash: str | None = Field(default=None, max_length=128)
    double_opt_in: bool | None = None
    double_opt_in_at: datetime | None = None
    purpose: str | None = Field(default=None, max_length=120)
    data_retention_until: datetime | None = None

    @model_validator(mode="after")
    def validate_double_opt_in(self):
        if self.double_opt_in is False and self.double_opt_in_at is not None:
            raise ValueError("double_opt_in_at must be null when double_opt_in is false")
        return self
