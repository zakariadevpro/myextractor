import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditActionCount(BaseModel):
    action: str
    count: int


class AuditSummaryResponse(BaseModel):
    since_hours: int
    total_events: int
    unique_actors: int
    events_by_action: list[AuditActionCount]
