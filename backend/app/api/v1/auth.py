from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.auth_cookies import (
    clear_auth_cookies,
    enforce_csrf,
    extract_refresh_token,
    issue_auth_cookies,
)
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserMeResponse
from app.services.auth_service import AuthService
from app.services.permission_service import PermissionService
from app.services.rate_limit_service import RateLimitService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await RateLimitService().enforce_register(request, data.email)
    service = AuthService(db)
    tokens = await service.register(data)
    if settings.auth_cookie_mode:
        issue_auth_cookies(response, tokens.refresh_token)
    return tokens


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await RateLimitService().enforce_login(request, data.email)
    service = AuthService(db)
    tokens = await service.login(data)
    if settings.auth_cookie_mode:
        issue_auth_cookies(response, tokens.refresh_token)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await RateLimitService().enforce_refresh(request)
    enforce_csrf(request)
    service = AuthService(db)
    refresh_token_value = extract_refresh_token(request, data.refresh_token)
    tokens = await service.refresh(refresh_token_value)
    if settings.auth_cookie_mode:
        issue_auth_cookies(response, tokens.refresh_token)
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(
    data: LogoutRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    enforce_csrf(request)
    service = AuthService(db)
    refresh_token_value = extract_refresh_token(request, data.refresh_token)
    await service.logout(refresh_token_value)
    if settings.auth_cookie_mode:
        clear_auth_cookies(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch organization name explicitly to avoid async lazy-loading issues
    org_name = None
    if current_user.organization_id:
        result = await db.execute(
            select(Organization.name).where(Organization.id == current_user.organization_id)
        )
        org_name = result.scalar_one_or_none()

    effective_permissions = sorted(
        await PermissionService(db).get_effective_permissions(current_user)
    )

    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=current_user.role,
        is_active=current_user.is_active,
        organization_id=current_user.organization_id,
        created_at=current_user.created_at,
        organization_name=org_name,
        effective_permissions=effective_permissions,
    )
