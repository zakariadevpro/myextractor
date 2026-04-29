import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_manager
from app.core.roles import ROLE_SUPER_ADMIN
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit import AuditLogResponse, AuditSummaryResponse
from app.schemas.common import PaginatedResponse
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/audit", tags=["audit"])


def _scoped_org(user: User, requested_org: uuid.UUID | None) -> uuid.UUID | None:
    """Resolve which org scope to query.

    super_admin can pass ?organization_id=<uuid> to scope to one tenant, or
    omit it (or pass 'all') to see logs across every organization.
    All other roles are forced to their own org.
    """
    if user.role == ROLE_SUPER_ADMIN:
        return requested_org
    return user.organization_id


@router.get("/logs", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = Query(
        None,
        description="super_admin only: filter to a specific org. Omit to see all orgs.",
    ),
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    service = AuditLogService(db)
    logs, total = await service.list_logs(
        organization_id=_scoped_org(current_user, organization_id),
        page=page,
        page_size=page_size,
        action=action,
        resource_type=resource_type,
        actor_user_id=actor_user_id,
    )
    return PaginatedResponse(
        items=[AuditLogResponse(**log_item) for log_item in logs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/summary", response_model=AuditSummaryResponse)
async def get_audit_summary(
    since_hours: int = Query(24, ge=1, le=720),
    organization_id: uuid.UUID | None = Query(
        None,
        description="super_admin only: filter to a specific org. Omit to see all orgs.",
    ),
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    service = AuditLogService(db)
    data = await service.summary(
        organization_id=_scoped_org(current_user, organization_id),
        since_hours=since_hours,
    )
    return AuditSummaryResponse.model_validate(data)
