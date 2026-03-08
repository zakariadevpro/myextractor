import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.organization import Organization
from app.schemas.b2c import B2CLeadIntakeCreate
from app.schemas.lead import LeadResponse
from app.services.b2c_intake_service import B2CIntakeService
from app.services.meta_lead_ads_service import MetaLeadAdsService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _get_org_by_slug(db: AsyncSession, slug: str) -> Organization:
    result = await db.execute(select(Organization).where(Organization.slug == slug))
    organization = result.scalar_one_or_none()
    if not organization:
        raise NotFoundError("Organization not found")
    return organization


def _enforce_webhook_secret(secret_header: str | None):
    if not settings.b2c_webhook_secret:
        raise BadRequestError("B2C webhook secret is not configured")
    if not secret_header or not hmac.compare_digest(secret_header, settings.b2c_webhook_secret):
        raise ForbiddenError("Invalid webhook secret")


@router.post("/b2c/intake/{org_slug}", response_model=LeadResponse)
async def b2c_intake_webhook(
    org_slug: str,
    data: B2CLeadIntakeCreate,
    x_winaity_webhook_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not settings.b2c_mode_enabled:
        raise BadRequestError("B2C mode is disabled on this environment")

    _enforce_webhook_secret(x_winaity_webhook_secret)
    org = await _get_org_by_slug(db, org_slug)

    lead = await B2CIntakeService(db).intake_for_org(
        organization_id=org.id,
        data=data,
        actor_user_id=None,
        action="webhook.b2c_intake",
        source_context="webhook_b2c_intake",
    )
    return LeadResponse.model_validate(lead)


@router.get("/meta/lead-ads/{org_slug}", response_class=PlainTextResponse)
async def verify_meta_lead_ads_webhook(
    org_slug: str,
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    db: AsyncSession = Depends(get_db),
):
    if not settings.b2c_mode_enabled:
        raise BadRequestError("B2C mode is disabled on this environment")
    if not settings.meta_webhook_verify_token:
        raise BadRequestError("META_WEBHOOK_VERIFY_TOKEN is not configured")

    await _get_org_by_slug(db, org_slug)
    is_valid = (
        hub_mode == "subscribe"
        and hub_verify_token is not None
        and hmac.compare_digest(hub_verify_token, settings.meta_webhook_verify_token)
    )
    if not is_valid:
        raise ForbiddenError("Invalid verify token")

    return hub_challenge or ""


@router.post("/meta/lead-ads/{org_slug}")
async def intake_meta_lead_ads_webhook(
    org_slug: str,
    request: Request,
    x_winaity_webhook_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not settings.b2c_mode_enabled:
        raise BadRequestError("B2C mode is disabled on this environment")

    _enforce_webhook_secret(x_winaity_webhook_secret)
    org = await _get_org_by_slug(db, org_slug)
    payload = await request.json()

    processed_events = 0
    ingested = 0
    skipped = 0
    errors: list[str] = []

    mapper = MetaLeadAdsService(access_token=settings.meta_access_token)
    intake_service = B2CIntakeService(db)

    entries = payload.get("entry") or []
    for entry in entries:
        for change in entry.get("changes") or []:
            if change.get("field") != "leadgen":
                continue
            processed_events += 1
            value = change.get("value") or {}
            leadgen_id = value.get("leadgen_id")
            if not leadgen_id:
                skipped += 1
                errors.append("leadgen event without leadgen_id")
                continue

            try:
                if settings.meta_access_token:
                    lead_data = await mapper.fetch_lead(leadgen_id)
                    intake_payload = mapper.build_intake_payload(
                        leadgen_id=leadgen_id,
                        field_data_rows=lead_data.get("field_data"),
                        created_time=lead_data.get("created_time"),
                        campaign_name=lead_data.get("campaign_name"),
                        source_channel="facebook",
                    )
                else:
                    lead_data_inline: dict[str, Any] = value.get("lead_data") or {}
                    if not lead_data_inline:
                        skipped += 1
                        errors.append(
                            f"leadgen_id {leadgen_id}: no META_ACCESS_TOKEN and no inline lead_data"
                        )
                        continue

                    intake_payload = mapper.build_intake_payload(
                        leadgen_id=leadgen_id,
                        field_data_rows=lead_data_inline.get("field_data"),
                        created_time=(
                            lead_data_inline.get("created_time") or value.get("created_time")
                        ),
                        campaign_name=lead_data_inline.get("campaign_name"),
                        source_channel="facebook",
                    )

                await intake_service.intake_for_org(
                    organization_id=org.id,
                    data=intake_payload,
                    actor_user_id=None,
                    action="webhook.meta_lead_ads.intake",
                    source_context="meta_lead_ads_webhook",
                )
                ingested += 1
            except Exception as exc:
                skipped += 1
                errors.append(f"leadgen_id {leadgen_id}: {str(exc)[:180]}")

    return {
        "received": True,
        "processed_events": processed_events,
        "ingested": ingested,
        "skipped": skipped,
        "errors": errors[:20],
    }
