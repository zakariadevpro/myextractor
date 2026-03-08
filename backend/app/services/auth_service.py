import uuid
from datetime import datetime, timezone

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, UnauthorizedError
from app.core.roles import ROLE_SUPER_ADMIN
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.redis import redis_client
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.audit_log_service import AuditLogService


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest) -> TokenResponse:
        # Check existing user
        existing = await self.db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise BadRequestError("Email already registered")

        # Create organization
        slug = slugify(data.organization_name)
        # Ensure unique slug
        existing_org = await self.db.execute(select(Organization).where(Organization.slug == slug))
        if existing_org.scalar_one_or_none():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        org = Organization(name=data.organization_name, slug=slug)
        self.db.add(org)
        await self.db.flush()

        # Create tenant owner as super admin.
        user = User(
            organization_id=org.id,
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            role=ROLE_SUPER_ADMIN,
        )
        self.db.add(user)
        await self.db.flush()
        await AuditLogService(self.db).log(
            action="auth.register",
            organization_id=org.id,
            actor_user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            details={"email": user.email},
        )

        return self._create_tokens(user)

    async def login(self, data: LoginRequest) -> TokenResponse:
        result = await self.db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")

        user.last_login_at = datetime.now(timezone.utc)
        await AuditLogService(self.db).log(
            action="auth.login",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
        )
        return self._create_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid refresh token")

        user_id = payload.get("sub")
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not user_id or not jti or not exp:
            raise UnauthorizedError("Invalid refresh token payload")

        if await self._is_refresh_token_revoked(jti):
            raise UnauthorizedError("Refresh token already used")

        result = await self.db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive")

        await self._revoke_refresh_token(jti, int(exp))
        return self._create_tokens(user)

    async def logout(self, refresh_token: str) -> None:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            return
        user_id = payload.get("sub")
        org_id = payload.get("org")
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            return
        await self._revoke_refresh_token(str(jti), int(exp))
        await AuditLogService(self.db).log(
            action="auth.logout",
            organization_id=uuid.UUID(org_id) if org_id else None,
            actor_user_id=uuid.UUID(user_id) if user_id else None,
            resource_type="user",
            resource_id=str(user_id) if user_id else None,
        )

    def _create_tokens(self, user: User) -> TokenResponse:
        token_data = {"sub": str(user.id), "org": str(user.organization_id), "role": user.role}
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )

    async def _is_refresh_token_revoked(self, jti: str) -> bool:
        try:
            return bool(await redis_client.get(f"auth:refresh:revoked:{jti}"))
        except Exception:
            # Fail closed for refresh rotation security.
            raise UnauthorizedError("Unable to validate refresh token")

    async def _revoke_refresh_token(self, jti: str, exp_ts: int) -> None:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        ttl = max(exp_ts - now_ts, 1)
        try:
            await redis_client.setex(f"auth:refresh:revoked:{jti}", ttl, "1")
        except Exception:
            # Fail closed for refresh rotation security.
            raise UnauthorizedError("Unable to rotate refresh token")
