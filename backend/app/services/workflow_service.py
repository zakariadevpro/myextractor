import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.automation_workflow import AutomationWorkflow
from app.models.lead import Lead
from app.schemas.workflow import WorkflowCreate, WorkflowRunResult, WorkflowUpdate

ALLOWED_TRIGGER_EVENTS = {"post_extraction", "manual"}
ALLOWED_WORKFLOW_ACTIONS = {"score_delta", "set_lead_kind", "mark_duplicate", "set_source"}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_conditions(raw_conditions: dict[str, Any]) -> dict[str, Any]:
    conditions = dict(raw_conditions or {})
    normalized: dict[str, Any] = {}

    for key in ("min_score", "max_score"):
        if key in conditions and conditions[key] is not None:
            try:
                normalized[key] = int(conditions[key])
            except (TypeError, ValueError) as exc:
                raise BadRequestError(f"Condition '{key}' must be an integer") from exc

    if "lead_kind" in conditions and conditions["lead_kind"] is not None:
        lead_kind = str(conditions["lead_kind"]).strip().lower()
        if lead_kind not in {"b2b", "b2c"}:
            raise BadRequestError("Condition 'lead_kind' must be 'b2b' or 'b2c'")
        normalized["lead_kind"] = lead_kind

    if "source_in" in conditions and conditions["source_in"] is not None:
        source_in = conditions["source_in"]
        if not isinstance(source_in, list):
            raise BadRequestError("Condition 'source_in' must be a list")
        normalized["source_in"] = [str(item).strip() for item in source_in if str(item).strip()]

    if "city_contains" in conditions and conditions["city_contains"] is not None:
        normalized["city_contains"] = str(conditions["city_contains"]).strip().lower()

    for key in ("has_email", "has_phone", "is_duplicate"):
        if key in conditions and conditions[key] is not None:
            normalized[key] = _to_bool(conditions[key])

    return normalized


def _normalize_actions(raw_actions: dict[str, Any]) -> dict[str, Any]:
    actions = dict(raw_actions or {})
    unknown_keys = [key for key in actions if key not in ALLOWED_WORKFLOW_ACTIONS]
    if unknown_keys:
        raise BadRequestError(f"Unknown workflow actions: {', '.join(sorted(unknown_keys))}")

    normalized: dict[str, Any] = {}
    if "score_delta" in actions and actions["score_delta"] is not None:
        try:
            score_delta = int(actions["score_delta"])
        except (TypeError, ValueError) as exc:
            raise BadRequestError("Action 'score_delta' must be an integer") from exc
        normalized["score_delta"] = max(-100, min(100, score_delta))

    if "set_lead_kind" in actions and actions["set_lead_kind"] is not None:
        lead_kind = str(actions["set_lead_kind"]).strip().lower()
        if lead_kind not in {"b2b", "b2c"}:
            raise BadRequestError("Action 'set_lead_kind' must be 'b2b' or 'b2c'")
        normalized["set_lead_kind"] = lead_kind

    if "mark_duplicate" in actions and actions["mark_duplicate"] is not None:
        normalized["mark_duplicate"] = _to_bool(actions["mark_duplicate"])

    if "set_source" in actions and actions["set_source"] is not None:
        set_source = str(actions["set_source"]).strip()
        if not set_source:
            raise BadRequestError("Action 'set_source' cannot be empty")
        normalized["set_source"] = set_source

    if not normalized:
        raise BadRequestError("At least one action is required")

    return normalized


def _lead_matches_conditions(lead: Lead, conditions: dict[str, Any]) -> bool:
    min_score = conditions.get("min_score")
    if min_score is not None and lead.quality_score < min_score:
        return False

    max_score = conditions.get("max_score")
    if max_score is not None and lead.quality_score > max_score:
        return False

    lead_kind = conditions.get("lead_kind")
    if lead_kind and lead.lead_kind != lead_kind:
        return False

    source_in = conditions.get("source_in")
    if source_in and lead.source not in source_in:
        return False

    city_contains = conditions.get("city_contains")
    if city_contains and city_contains not in (lead.city or "").lower():
        return False

    has_email = conditions.get("has_email")
    if has_email is not None and bool(lead.emails) != bool(has_email):
        return False

    has_phone = conditions.get("has_phone")
    if has_phone is not None and bool(lead.phones) != bool(has_phone):
        return False

    is_duplicate = conditions.get("is_duplicate")
    if is_duplicate is not None and lead.is_duplicate != bool(is_duplicate):
        return False

    return True


def _apply_actions(lead: Lead, actions: dict[str, Any]) -> bool:
    changed = False
    score_delta = actions.get("score_delta")
    if score_delta is not None:
        new_score = max(0, min(100, lead.quality_score + int(score_delta)))
        if new_score != lead.quality_score:
            lead.quality_score = new_score
            changed = True

    set_lead_kind = actions.get("set_lead_kind")
    if set_lead_kind and set_lead_kind != lead.lead_kind:
        lead.lead_kind = set_lead_kind
        changed = True

    if "mark_duplicate" in actions:
        new_duplicate = bool(actions["mark_duplicate"])
        if new_duplicate != lead.is_duplicate:
            lead.is_duplicate = new_duplicate
            changed = True

    set_source = actions.get("set_source")
    if set_source and set_source != lead.source:
        lead.source = set_source
        changed = True

    return changed


class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_workflows(self, org_id: uuid.UUID) -> list[AutomationWorkflow]:
        result = await self.db.execute(
            select(AutomationWorkflow)
            .where(AutomationWorkflow.organization_id == org_id)
            .order_by(AutomationWorkflow.created_at.desc())
        )
        return result.scalars().all()

    async def create_workflow(
        self, org_id: uuid.UUID, actor_user_id: uuid.UUID, data: WorkflowCreate
    ) -> AutomationWorkflow:
        trigger = data.trigger_event.strip().lower()
        if trigger not in ALLOWED_TRIGGER_EVENTS:
            raise BadRequestError(
                f"trigger_event must be one of: {', '.join(sorted(ALLOWED_TRIGGER_EVENTS))}"
            )

        workflow = AutomationWorkflow(
            organization_id=org_id,
            created_by=actor_user_id,
            name=data.name.strip(),
            trigger_event=trigger,
            is_active=data.is_active,
            conditions=_normalize_conditions(data.conditions),
            actions=_normalize_actions(data.actions),
        )
        self.db.add(workflow)
        await self.db.flush()
        return workflow

    async def update_workflow(
        self, org_id: uuid.UUID, workflow_id: uuid.UUID, data: WorkflowUpdate
    ) -> AutomationWorkflow:
        result = await self.db.execute(
            select(AutomationWorkflow).where(
                AutomationWorkflow.id == workflow_id,
                AutomationWorkflow.organization_id == org_id,
            )
        )
        workflow = result.scalar_one_or_none()
        if not workflow:
            raise NotFoundError("Workflow not found")

        patch = data.model_dump(exclude_unset=True)
        if "name" in patch and patch["name"] is not None:
            workflow.name = patch["name"].strip()
        if "trigger_event" in patch and patch["trigger_event"] is not None:
            trigger = str(patch["trigger_event"]).strip().lower()
            if trigger not in ALLOWED_TRIGGER_EVENTS:
                raise BadRequestError(
                    f"trigger_event must be one of: {', '.join(sorted(ALLOWED_TRIGGER_EVENTS))}"
                )
            workflow.trigger_event = trigger
        if "is_active" in patch and patch["is_active"] is not None:
            workflow.is_active = bool(patch["is_active"])
        if "conditions" in patch and patch["conditions"] is not None:
            workflow.conditions = _normalize_conditions(patch["conditions"])
        if "actions" in patch and patch["actions"] is not None:
            workflow.actions = _normalize_actions(patch["actions"])

        await self.db.flush()
        return workflow

    async def run_workflows(
        self,
        *,
        org_id: uuid.UUID,
        trigger_event: str,
        extraction_job_id: uuid.UUID | None = None,
        dry_run: bool = False,
    ) -> list[WorkflowRunResult]:
        result = await self.db.execute(
            select(AutomationWorkflow).where(
                AutomationWorkflow.organization_id == org_id,
                AutomationWorkflow.is_active.is_(True),
                AutomationWorkflow.trigger_event == trigger_event,
            )
        )
        workflows = result.scalars().all()
        if not workflows:
            return []

        lead_query = (
            select(Lead)
            .options(selectinload(Lead.emails), selectinload(Lead.phones))
            .where(Lead.organization_id == org_id)
        )
        if extraction_job_id:
            lead_query = lead_query.where(Lead.extraction_job_id == extraction_job_id)
        lead_result = await self.db.execute(lead_query)
        leads = lead_result.scalars().unique().all()

        now_utc = datetime.now(timezone.utc)
        outcomes: list[WorkflowRunResult] = []
        for workflow in workflows:
            matched = 0
            updated = 0
            for lead in leads:
                if not _lead_matches_conditions(lead, workflow.conditions or {}):
                    continue
                matched += 1
                if not dry_run and _apply_actions(lead, workflow.actions or {}):
                    updated += 1

            if not dry_run:
                workflow.last_run_at = now_utc
            outcomes.append(
                WorkflowRunResult(
                    workflow_id=workflow.id,
                    matched=matched,
                    updated=updated,
                    dry_run=dry_run,
                )
            )

        return outcomes
