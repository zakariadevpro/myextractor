import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyRevokeResponse,
)
from app.services.api_key_service import ApiKeyService
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    keys = await ApiKeyService(db).list_keys(current_user.organization_id)
    return [ApiKeyResponse.model_validate(key) for key in keys]


@router.post("", response_model=ApiKeyCreateResponse)
async def create_api_key(
    data: ApiKeyCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    raw_key, key = await ApiKeyService(db).create_key(
        current_user.organization_id,
        current_user.id,
        data,
    )
    await AuditLogService(db).log(
        action="apikey.create",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="api_key",
        resource_id=str(key.id),
        details={
            "name": key.name,
            "scopes": key.scopes,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        },
    )
    return ApiKeyCreateResponse(api_key=raw_key, key=ApiKeyResponse.model_validate(key))


@router.post("/{key_id}/revoke", response_model=ApiKeyRevokeResponse)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    key = await ApiKeyService(db).revoke_key(current_user.organization_id, key_id)
    await AuditLogService(db).log(
        action="apikey.revoke",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="api_key",
        resource_id=str(key.id),
        details={"name": key.name},
    )
    return ApiKeyRevokeResponse(message="API key revoked")
