import uuid

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.roles import ROLE_ADMIN, ROLE_MANAGER, has_minimum_role
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.api_key_service import ApiKeyIdentity, ApiKeyService

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Invalid token payload")

    result = await db.execute(
        select(User).options(selectinload(User.organization)).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not has_minimum_role(user.role, ROLE_ADMIN):
        raise ForbiddenError("Admin role required")
    return user


async def get_current_manager(user: User = Depends(get_current_user)) -> User:
    if not has_minimum_role(user.role, ROLE_MANAGER):
        raise ForbiddenError("Manager role or higher required")
    return user


async def _get_api_key_identity(
    required_scope: str | None,
    x_api_key: str | None,
    db: AsyncSession,
) -> ApiKeyIdentity:
    if not x_api_key:
        raise UnauthorizedError("Missing X-API-Key header")
    return await ApiKeyService(db).authenticate(x_api_key, required_scope=required_scope)


def require_api_key_scope(required_scope: str | None = None):
    async def dependency(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        db: AsyncSession = Depends(get_db),
    ) -> ApiKeyIdentity:
        return await _get_api_key_identity(required_scope, x_api_key, db)

    return dependency
