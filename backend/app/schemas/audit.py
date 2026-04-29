import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    organization_name: str | None = None
    actor_user_id: uuid.UUID | None
    actor_name: str | None = None
    actor_email: str | None = None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditActionCount(BaseModel):
    action: str
    count: int


class AuditExtractionMetrics(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    running_jobs: int
    success_rate_pct: float
    avg_leads_found: float
    avg_duration_seconds: float
    filtered_non_b2b_total: int
    filtered_out_total: int
    classified_b2b_total: int
    classified_b2c_total: int


class AuditSummaryResponse(BaseModel):
    since_hours: int
    total_events: int
    unique_actors: int
    events_by_action: list[AuditActionCount]
    extraction_metrics: AuditExtractionMetrics
