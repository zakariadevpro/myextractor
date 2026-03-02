import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_manager
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.roles import ROLE_SUPER_ADMIN
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import UserCreate, UserCreateResponse, UserResponse, UserUpdate
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    base_query = select(User).where(User.organization_id == current_user.organization_id)

    total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(base_query.offset(offset).limit(page_size).order_by(User.created_at))
    users = result.scalars().all()

    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=UserCreateResponse)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if data.role == ROLE_SUPER_ADMIN and current_user.role != ROLE_SUPER_ADMIN:
        raise ForbiddenError("Only a super admin can assign super admin role")

    # Generate a temporary password (user should reset)
    import secrets

    temp_password = secrets.token_urlsafe(12)

    existing_result = await db.execute(select(User).where(User.email == data.email))
    if existing_result.scalar_one_or_none():
        raise BadRequestError("Email already registered")

    user = User(
        organization_id=current_user.organization_id,
        email=data.email,
        password_hash=hash_password(temp_password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await AuditLogService(db).log(
        action="user.create",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="user",
        resource_id=str(user.id),
        details={"role": user.role, "email": user.email},
    )
    return UserCreateResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        is_active=user.is_active,
        organization_id=user.organization_id,
        created_at=user.created_at,
        temporary_password=temp_password,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(
            User.id == user_id, User.organization_id == current_user.organization_id
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    if user.role == ROLE_SUPER_ADMIN and current_user.role != ROLE_SUPER_ADMIN:
        raise ForbiddenError("Only a super admin can manage another super admin")
    if data.role == ROLE_SUPER_ADMIN and current_user.role != ROLE_SUPER_ADMIN:
        raise ForbiddenError("Only a super admin can assign super admin role")
    if user.id == current_user.id and data.role and data.role != current_user.role:
        raise BadRequestError("Cannot change your own role")
    if user.id == current_user.id and data.is_active is False:
        raise BadRequestError("Cannot deactivate yourself")

    if user.role == ROLE_SUPER_ADMIN and data.role and data.role != ROLE_SUPER_ADMIN:
        active_super_admins_result = await db.execute(
            select(func.count()).where(
                User.organization_id == current_user.organization_id,
                User.role == ROLE_SUPER_ADMIN,
                User.is_active.is_(True),
            )
        )
        active_super_admins = active_super_admins_result.scalar() or 0
        if active_super_admins <= 1:
            raise BadRequestError("Cannot remove the last active super admin role")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.flush()
    await AuditLogService(db).log(
        action="user.update",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="user",
        resource_id=str(user.id),
        details={"updated_fields": list(data.model_dump(exclude_unset=True).keys())},
    )
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(
            User.id == user_id, User.organization_id == current_user.organization_id
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    if user.id == current_user.id:
        raise BadRequestError("Cannot deactivate yourself")
    if user.role == ROLE_SUPER_ADMIN and current_user.role != ROLE_SUPER_ADMIN:
        raise ForbiddenError("Only a super admin can deactivate a super admin")
    if user.role == ROLE_SUPER_ADMIN:
        active_super_admins_result = await db.execute(
            select(func.count()).where(
                User.organization_id == current_user.organization_id,
                User.role == ROLE_SUPER_ADMIN,
                User.is_active.is_(True),
            )
        )
        active_super_admins = active_super_admins_result.scalar() or 0
        if active_super_admins <= 1:
            raise BadRequestError("Cannot deactivate the last active super admin")

    user.is_active = False
    await db.flush()
    await AuditLogService(db).log(
        action="user.deactivate",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="user",
        resource_id=str(user.id),
    )
    return MessageResponse(message="User deactivated")
