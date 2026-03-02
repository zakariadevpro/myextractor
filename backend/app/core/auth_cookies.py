import secrets

from fastapi import Request, Response

from app.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError


def _cookie_common() -> dict:
    return {
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "domain": settings.auth_cookie_domain,
        "path": settings.auth_cookie_path,
    }


def issue_auth_cookies(response: Response, refresh_token: str) -> str:
    csrf_token = secrets.token_urlsafe(32)
    max_age = settings.refresh_token_expire_days * 24 * 60 * 60
    common = _cookie_common()

    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        max_age=max_age,
        **common,
    )
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        max_age=max_age,
        **common,
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    common = _cookie_common()
    response.delete_cookie(key=settings.auth_refresh_cookie_name, **common)
    response.delete_cookie(key=settings.auth_csrf_cookie_name, **common)


def extract_refresh_token(request: Request, body_refresh_token: str | None) -> str:
    if body_refresh_token:
        return body_refresh_token

    if settings.auth_cookie_mode:
        token = request.cookies.get(settings.auth_refresh_cookie_name)
        if token:
            return token
        raise UnauthorizedError("Missing refresh token")

    raise UnauthorizedError("Missing refresh token")


def enforce_csrf(request: Request) -> None:
    if not settings.auth_cookie_mode:
        return

    csrf_cookie = request.cookies.get(settings.auth_csrf_cookie_name)
    csrf_header = request.headers.get(settings.auth_csrf_header_name)
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise ForbiddenError("Invalid CSRF token")
