import uuid
from datetime import datetime

from pydantic import BaseModel, Field

ALLOWED_API_KEY_SCOPES = {
    "leads:read",
    "leads:export",
    "extractions:run",
    "workflows:run",
    "scoring:read",
}


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: ["leads:read"])
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(BaseModel):
    api_key: str
    key: ApiKeyResponse


class ApiKeyRevokeResponse(BaseModel):
    message: str
