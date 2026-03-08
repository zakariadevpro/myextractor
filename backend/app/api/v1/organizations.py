from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationResponse, OrganizationUpdateRequest
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/organizations", tags=["organizations"])


async def _build_organization_response(db: AsyncSession, organization_id) -> OrganizationResponse:
    result = await db.execute(
        select(
            Organization.id,
            Organization.name,
            Organization.slug,
            Organization.is_active,
            Organization.created_at,
            Organization.updated_at,
        ).where(Organization.id == organization_id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundError("Organization not found")

    return OrganizationResponse(
        id=row.id,
        name=row.name,
        slug=row.slug,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/me", response_model=OrganizationResponse)
async def get_my_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _build_organization_response(db, current_user.organization_id)


@router.patch("/me", response_model=OrganizationResponse)
async def update_my_organization(
    data: OrganizationUpdateRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    organization = result.scalar_one_or_none()
    if not organization:
        raise NotFoundError("Organization not found")

    old_name = organization.name
    organization.name = data.organization_name.strip()
    await db.flush()
    await AuditLogService(db).log(
        action="organization.update_settings",
        organization_id=organization.id,
        actor_user_id=current_user.id,
        resource_type="organization",
        resource_id=str(organization.id),
        details={"old_name": old_name, "new_name": organization.name},
    )
    return await _build_organization_response(db, organization.id)
