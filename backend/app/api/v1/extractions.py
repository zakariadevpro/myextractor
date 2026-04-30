import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models.extraction import ExtractionJob
from app.models.lead import Lead
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.extraction import ExtractionCreate, ExtractionResponse
from app.services.audit_log_service import AuditLogService
from app.services.cleaning_service import CleaningService
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


@router.delete("/{job_id}", response_model=MessageResponse)
async def delete_extraction(
    job_id: uuid.UUID,
    delete_leads: bool = Query(
        False,
        description="If true, also delete all leads attached to this extraction job.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    perm_service = PermissionService(db)
    await perm_service.require_user_permission(current_user, "extraction.cancel")
    if delete_leads:
        await perm_service.require_user_permission(current_user, "leads.manage")

    result = await db.execute(
        select(ExtractionJob).where(
            ExtractionJob.id == job_id,
            ExtractionJob.organization_id == current_user.organization_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("Extraction job not found")
    if job.status in ("pending", "running"):
        raise BadRequestError(
            "Annule ce job avant de le supprimer (status pending/running)."
        )

    leads_deleted = 0
    if delete_leads:
        leads_q = await db.execute(
            select(func.count())
            .select_from(Lead)
            .where(
                Lead.extraction_job_id == job_id,
                Lead.organization_id == current_user.organization_id,
            )
        )
        leads_deleted = int(leads_q.scalar() or 0)
        await db.execute(
            delete(Lead).where(
                Lead.extraction_job_id == job_id,
                Lead.organization_id == current_user.organization_id,
            )
        )
    else:
        # Detach surviving leads so the FK doesn't block the job delete.
        await db.execute(
            update(Lead)
            .where(
                Lead.extraction_job_id == job_id,
                Lead.organization_id == current_user.organization_id,
            )
            .values(extraction_job_id=None)
        )

    job_id_str = str(job.id)
    await db.delete(job)
    await db.flush()

    # Recompute is_duplicate / is_similar flags so survivors that lost their
    # twins go back to "unique". Otherwise the card keeps showing stale flags
    # set by the auto-dedupe at extraction time.
    if delete_leads and leads_deleted > 0:
        await CleaningService(db).deduplicate(current_user.organization_id)

    await AuditLogService(db).log(
        action="extraction.delete",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="extraction_job",
        resource_id=job_id_str,
        details={
            "delete_leads": delete_leads,
            "leads_deleted": leads_deleted,
        },
    )
    suffix = (
        f" et {leads_deleted} lead(s) supprime(s)" if delete_leads else " (leads conserves)"
    )
    return MessageResponse(message=f"Extraction supprimee{suffix}.")
