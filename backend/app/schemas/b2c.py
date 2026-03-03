from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

B2CConsentSource = Literal[
    "web_form",
    "meta_lead_ads",
    "google_lead_form",
    "partner_api",
    "crm_import",
]
B2CSourceChannel = Literal["web", "facebook", "instagram", "google", "tiktok", "partner", "import"]


class B2CLeadIntakeCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    city: str | None = Field(default=None, max_length=255)
    consent_source: B2CConsentSource
    consent_at: datetime
    consent_text_version: str = Field(..., min_length=1, max_length=50)
    consent_proof_ref: str = Field(..., min_length=1, max_length=255)
    privacy_policy_version: str = Field(..., min_length=1, max_length=50)
    source_campaign: str | None = Field(default=None, max_length=255)
    source_channel: B2CSourceChannel | None = None
    purpose: str = Field(default="prospection_commerciale", max_length=120)
    double_opt_in: bool = False
    double_opt_in_at: datetime | None = None
    data_retention_until: datetime | None = None

    @model_validator(mode="after")
    def validate_channels(self):
        if not self.email and not self.phone:
            raise ValueError("email or phone is required")
        if self.double_opt_in and self.double_opt_in_at is None:
            self.double_opt_in_at = self.consent_at
        return self
