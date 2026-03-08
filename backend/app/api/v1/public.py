from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_api_key_scope
from app.db.session import get_db
from app.models.lead import Lead
from app.models.lead_consent import LeadConsent
from app.schemas.lead import LeadResponse
from app.services.api_key_service import ApiKeyIdentity

router = APIRouter(prefix="/public", tags=["public-api"])


@router.get("/leads", response_model=list[LeadResponse])
async def public_list_leads(
    min_score: int = Query(default=0, ge=0, le=100),
    max_score: int = Query(default=100, ge=0, le=100),
    lead_kind: Literal["b2b", "b2c"] | None = None,
    source: str | None = None,
    city: str | None = None,
    sector: str | None = None,
    limit: int = Query(default=200, ge=1, le=5000),
    api_key: ApiKeyIdentity = Depends(require_api_key_scope("leads:read")),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Lead)
        .options(selectinload(Lead.emails), selectinload(Lead.phones), selectinload(Lead.consent))
        .where(
            Lead.organization_id == api_key.organization_id,
            Lead.quality_score >= min_score,
            Lead.quality_score <= max_score,
        )
    )
    if lead_kind:
        query = query.where(Lead.lead_kind == lead_kind)
    if source:
        query = query.where(Lead.source == source)
    if city:
        query = query.where(Lead.city.ilike(f"%{city}%"))
    if sector:
        query = query.where(Lead.sector.ilike(f"%{sector}%"))

    query = query.order_by(Lead.quality_score.desc(), Lead.created_at.desc()).limit(limit)
    result = await db.execute(query)
    leads = result.scalars().unique().all()
    return [LeadResponse.model_validate(lead) for lead in leads]


@router.get("/leads/export/csv")
async def public_export_leads_csv(
    min_score: int = Query(default=0, ge=0, le=100),
    lead_kind: Literal["b2b", "b2c"] | None = None,
    consent_granted_only: bool = False,
    limit: int = Query(default=10000, ge=1, le=10000),
    api_key: ApiKeyIdentity = Depends(require_api_key_scope("leads:export")),
    db: AsyncSession = Depends(get_db),
):
    import csv
    import io

    query = (
        select(Lead)
        .options(selectinload(Lead.emails), selectinload(Lead.phones))
        .where(
            Lead.organization_id == api_key.organization_id,
            Lead.quality_score >= min_score,
        )
    )
    if lead_kind:
        query = query.where(Lead.lead_kind == lead_kind)
    if consent_granted_only:
        now_utc = datetime.now(timezone.utc)
        query = query.join(LeadConsent, LeadConsent.lead_id == Lead.id).where(
            LeadConsent.consent_status == "granted",
            LeadConsent.lawful_basis == "consent",
            or_(
                LeadConsent.data_retention_until.is_(None),
                LeadConsent.data_retention_until > now_utc,
            ),
        )
    query = query.order_by(Lead.quality_score.desc(), Lead.created_at.desc()).limit(limit)

    result = await db.execute(query)
    leads = result.scalars().unique().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Entreprise",
            "Secteur",
            "Email",
            "Telephone",
            "Ville",
            "Code Postal",
            "Score",
            "Source",
            "Site Web",
            "SIREN",
            "Type Lead",
        ]
    )
    for lead in leads:
        primary_email = next((e.email for e in lead.emails if e.is_primary), "")
        if not primary_email and lead.emails:
            primary_email = lead.emails[0].email
        primary_phone = next(
            (p.phone_normalized or p.phone_raw for p in lead.phones if p.is_primary),
            "",
        )
        if not primary_phone and lead.phones:
            primary_phone = lead.phones[0].phone_normalized or lead.phones[0].phone_raw or ""

        writer.writerow(
            [
                lead.company_name or "",
                lead.sector or "",
                primary_email or "",
                primary_phone or "",
                lead.city or "",
                lead.postal_code or "",
                lead.quality_score,
                lead.source or "",
                lead.website or "",
                lead.siren or "",
                lead.lead_kind or "b2b",
            ]
        )

    from fastapi.responses import StreamingResponse

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename="
                f"public_leads_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            )
        },
    )
