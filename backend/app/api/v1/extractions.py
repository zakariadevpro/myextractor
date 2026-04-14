import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models.extraction import ExtractionJob
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.extraction import ExtractionCreate, ExtractionResponse
from app.services.audit_log_service import AuditLogService
from app.services.extraction_service import ExtractionService
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/extractions", tags=["extractions"])

ALLOWED_EXTRACTION_SORT_COLUMNS = {
    "created_at": ExtractionJob.created_at,
    "status": ExtractionJob.status,
    "progress": ExtractionJob.progress,
}


@router.post("", response_model=ExtractionResponse)
async def create_extraction(
    data: ExtractionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await PermissionService(db).require_user_permission(current_user, "extraction.create")
    service = ExtractionService(db)
    job = await service.create_job(data, current_user)
    await AuditLogService(db).log(
        action="extraction.create",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="extraction_job",
        resource_id=str(job.id),
        details={
            "source": data.source,
            "target_kind": data.target_kind,
            "keywords_count": len(job.keywords or []),
            "max_leads": data.max_leads,
        },
    )
    # Commit first so the worker can find the job in DB
    await db.commit()
    # Now dispatch to Celery (job is visible in DB)
    try:
        service.dispatch_job()
    except Exception:
        job.status = "failed"
        job.error_message = "Failed to dispatch scraping task to worker queue"
        await db.commit()
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail="Scraping task could not be dispatched")
    return ExtractionResponse.model_validate(job)


@router.get("", response_model=PaginatedResponse[ExtractionResponse])
async def list_extractions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    ordering: str | None = Query(None, description="Ex: -created_at, status, progress"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await PermissionService(db).require_user_permission(current_user, "extraction.view")
    offset = (page - 1) * page_size
    base_query = select(ExtractionJob).where(
        ExtractionJob.organization_id == current_user.organization_id
    )
    if status:
        base_query = base_query.where(ExtractionJob.status == status)

    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    sort_order = "desc" if not ordering or ordering.startswith("-") else "asc"
    sort_key = (ordering or "-created_at").lstrip("-")
    sort_col = ALLOWED_EXTRACTION_SORT_COLUMNS.get(sort_key, ExtractionJob.created_at)
    if sort_order == "desc":
        base_query = base_query.order_by(sort_col.desc())
    else:
        base_query = base_query.order_by(sort_col.asc())

    result = await db.execute(base_query.offset(offset).limit(page_size))
    jobs = result.scalars().all()

    return PaginatedResponse(
        items=[ExtractionResponse.model_validate(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{job_id}", response_model=ExtractionResponse)
async def get_extraction(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await PermissionService(db).require_user_permission(current_user, "extraction.view")
    result = await db.execute(
        select(ExtractionJob).where(
            ExtractionJob.id == job_id,
            ExtractionJob.organization_id == current_user.organization_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("Extraction job not found")
    return ExtractionResponse.model_validate(job)


@router.post("/{job_id}/cancel", response_model=MessageResponse)
async def cancel_extraction(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await PermissionService(db).require_user_permission(current_user, "extraction.cancel")
    result = await db.execute(
        select(ExtractionJob).where(
            ExtractionJob.id == job_id,
            ExtractionJob.organization_id == current_user.organization_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("Extraction job not found")
    if job.status not in ("pending", "running"):
        raise BadRequestError("Job cannot be cancelled in its current state")

    job.status = "cancelled"
    await db.flush()
    await AuditLogService(db).log(
        action="extraction.cancel",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="extraction_job",
        resource_id=str(job.id),
    )
    return MessageResponse(message="Extraction job cancelled")
