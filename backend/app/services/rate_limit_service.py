import hashlib

from fastapi import Request

from app.config import settings
from app.core.exceptions import UsageLimitError
from app.db.redis import redis_client


class RateLimitService:
    def _client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _email_hash(self, email: str | None) -> str:
        if not email:
            return "none"
        return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]

    async def _enforce(self, key: str, limit: int, window_seconds: int) -> None:
        if limit <= 0:
            return
        try:
            current = await redis_client.incr(key)
            if current == 1:
                await redis_client.expire(key, window_seconds)
        except Exception:
            # Fail-open to preserve auth availability if Redis is temporarily unavailable.
            return

        if current > limit:
            raise UsageLimitError("Too many requests. Please retry later.")

    async def enforce_login(self, request: Request, email: str) -> None:
        ip = self._client_ip(request)
        email_hash = self._email_hash(email)
        await self._enforce(
            key=f"rate:auth:login:ip:{ip}",
            limit=settings.auth_login_rate_limit,
            window_seconds=settings.auth_login_window_seconds,
        )
        await self._enforce(
            key=f"rate:auth:login:email:{email_hash}",
            limit=settings.auth_login_rate_limit,
            window_seconds=settings.auth_login_window_seconds,
        )

    async def enforce_register(self, request: Request, email: str) -> None:
        ip = self._client_ip(request)
        email_hash = self._email_hash(email)
        await self._enforce(
            key=f"rate:auth:register:ip:{ip}",
            limit=settings.auth_register_rate_limit,
            window_seconds=settings.auth_register_window_seconds,
        )
        await self._enforce(
            key=f"rate:auth:register:email:{email_hash}",
            limit=settings.auth_register_rate_limit,
            window_seconds=settings.auth_register_window_seconds,
        )

    async def enforce_refresh(self, request: Request) -> None:
        ip = self._client_ip(request)
        await self._enforce(
            key=f"rate:auth:refresh:ip:{ip}",
            limit=settings.auth_refresh_rate_limit,
            window_seconds=settings.auth_refresh_window_seconds,
        )

