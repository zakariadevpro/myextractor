import uuid
from datetime import datetime

from pydantic import BaseModel


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    monthly_price_cents: int
    max_leads_per_month: int
    max_users: int
    max_extractions_per_day: int

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    plan: PlanResponse
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageResponse(BaseModel):
    leads_extracted: int = 0
    leads_exported: int = 0
    max_leads_per_month: int = 0
    usage_percentage: float = 0.0


class CheckoutRequest(BaseModel):
    plan_slug: str
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
