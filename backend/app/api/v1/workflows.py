import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.models.user import User
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
    WorkflowUpdate,
)
from app.services.audit_log_service import AuditLogService
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    items = await WorkflowService(db).list_workflows(current_user.organization_id)
    return [WorkflowResponse.model_validate(item) for item in items]


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    data: WorkflowCreate,
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    workflow = await WorkflowService(db).create_workflow(
        current_user.organization_id, current_user.id, data
    )
    await AuditLogService(db).log(
        action="workflow.create",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="workflow",
        resource_id=str(workflow.id),
        details={
            "name": workflow.name,
            "trigger_event": workflow.trigger_event,
            "conditions": workflow.conditions,
            "actions": workflow.actions,
            "is_active": workflow.is_active,
        },
    )
    return WorkflowResponse.model_validate(workflow)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    data: WorkflowUpdate,
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    workflow = await WorkflowService(db).update_workflow(
        current_user.organization_id, workflow_id, data
    )
    await AuditLogService(db).log(
        action="workflow.update",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="workflow",
        resource_id=str(workflow.id),
        details={
            "name": workflow.name,
            "trigger_event": workflow.trigger_event,
            "conditions": workflow.conditions,
            "actions": workflow.actions,
            "is_active": workflow.is_active,
        },
    )
    return WorkflowResponse.model_validate(workflow)


@router.post("/run", response_model=WorkflowRunResponse)
async def run_workflows(
    payload: WorkflowRunRequest,
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    details = await WorkflowService(db).run_workflows(
        org_id=current_user.organization_id,
        trigger_event="manual",
        extraction_job_id=payload.extraction_job_id,
        dry_run=payload.dry_run,
    )

    total_matched = sum(item.matched for item in details)
    total_updated = sum(item.updated for item in details)
    await AuditLogService(db).log(
        action="workflow.run_manual",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="workflow",
        details={
            "dry_run": payload.dry_run,
            "total_workflows": len(details),
            "total_matched": total_matched,
            "total_updated": total_updated,
            "extraction_job_id": (
                str(payload.extraction_job_id) if payload.extraction_job_id else None
            ),
        },
    )

    return WorkflowRunResponse(
        total_workflows=len(details),
        total_matched=total_matched,
        total_updated=total_updated,
        details=details,
    )
