import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError, UnauthorizedError
from app.models.api_key import ApiKey
from app.schemas.api_key import ALLOWED_API_KEY_SCOPES, ApiKeyCreate


@dataclass
class ApiKeyIdentity:
    organization_id: uuid.UUID
    api_key_id: uuid.UUID
    scopes: list[str]


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    # Prefix helps quick identification without leaking the full secret.
    return f"wk_live_{secrets.token_urlsafe(32)}"


def extract_key_prefix(raw_key: str) -> str:
    return raw_key[:18]


class ApiKeyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_keys(self, org_id: uuid.UUID) -> list[ApiKey]:
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.organization_id == org_id)
            .order_by(ApiKey.created_at.desc())
        )
        return result.scalars().all()

    async def create_key(self, org_id: uuid.UUID, actor_user_id: uuid.UUID, data: ApiKeyCreate):
        scopes = sorted(set(scope.strip() for scope in data.scopes if scope.strip()))
        if not scopes:
            raise BadRequestError("At least one API key scope is required")
        invalid = [scope for scope in scopes if scope not in ALLOWED_API_KEY_SCOPES]
        if invalid:
            raise BadRequestError(f"Invalid scopes: {', '.join(invalid)}")

        raw_key = generate_api_key()
        key = ApiKey(
            organization_id=org_id,
            created_by=actor_user_id,
            name=data.name.strip(),
            key_prefix=extract_key_prefix(raw_key),
            key_hash=hash_api_key(raw_key),
            scopes=scopes,
            is_active=True,
            expires_at=data.expires_at,
        )
        self.db.add(key)
        await self.db.flush()
        return raw_key, key

    async def revoke_key(self, org_id: uuid.UUID, key_id: uuid.UUID):
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == org_id)
        )
        key = result.scalar_one_or_none()
        if not key:
            raise NotFoundError("API key not found")

        key.is_active = False
        key.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
        return key

    async def authenticate(self, raw_key: str, required_scope: str | None = None) -> ApiKeyIdentity:
        normalized = (raw_key or "").strip()
        if not normalized:
            raise UnauthorizedError("Missing API key")

        key_prefix = extract_key_prefix(normalized)
        key_hash = hash_api_key(normalized)
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.key_prefix == key_prefix, ApiKey.key_hash == key_hash)
        )
        key = result.scalar_one_or_none()
        if not key:
            raise UnauthorizedError("Invalid API key")

        now_utc = datetime.now(timezone.utc)
        if not key.is_active or (key.expires_at and key.expires_at <= now_utc):
            raise UnauthorizedError("API key inactive or expired")

        if required_scope and required_scope not in key.scopes:
            raise ForbiddenError(f"API key scope '{required_scope}' is required")

        key.last_used_at = now_utc
        await self.db.flush()
        return ApiKeyIdentity(
            organization_id=key.organization_id,
            api_key_id=key.id,
            scopes=key.scopes,
        )
