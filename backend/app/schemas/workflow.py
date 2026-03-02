import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

WorkflowTrigger = Literal["post_extraction", "manual"]


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    trigger_event: WorkflowTrigger = "post_extraction"
    is_active: bool = True
    conditions: dict[str, Any] = Field(default_factory=dict)
    actions: dict[str, Any] = Field(default_factory=dict)


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    trigger_event: WorkflowTrigger | None = None
    is_active: bool | None = None
    conditions: dict[str, Any] | None = None
    actions: dict[str, Any] | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    name: str
    trigger_event: WorkflowTrigger
    is_active: bool
    conditions: dict[str, Any]
    actions: dict[str, Any]
    last_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunRequest(BaseModel):
    extraction_job_id: uuid.UUID | None = None
    dry_run: bool = False


class WorkflowRunResult(BaseModel):
    workflow_id: uuid.UUID
    matched: int
    updated: int
    dry_run: bool


class WorkflowRunResponse(BaseModel):
    total_workflows: int
    total_matched: int
    total_updated: int
    details: list[WorkflowRunResult]
