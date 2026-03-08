import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationUpdateRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=255)
