import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models.lead import Lead
from app.models.lead_consent import LeadConsent
from app.models.user import User
from app.schemas.b2c import B2CCsvImportError, B2CCsvImportSummary, B2CLeadIntakeCreate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.lead import (
    LeadFilters,
    LeadResponse,
    LeadUpdate,
    SuggestedSegment,
    SuggestedSegmentResponse,
)
from app.schemas.lead_consent import LeadConsentResponse, LeadConsentUpdate
from app.services.audit_log_service import AuditLogService
from app.services.b2c_intake_service import B2CIntakeService
from app.services.permission_service import PermissionService
from app.services.scoring_service import ScoringService

router = APIRouter(prefix="/leads", tags=["leads"])

ALLOWED_LEAD_SORT_COLUMNS = {
    "created_at": Lead.created_at,
    "updated_at": Lead.updated_at,
    "quality_score": Lead.quality_score,
    "company_name": Lead.company_name,
    "city": Lead.city,
    "sector": Lead.sector,
}


def _sanitize_csv_cell(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


def _normalize_mapping_payload(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BadRequestError(f"Invalid mapping JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise BadRequestError("Mapping must be a JSON object")
    normalized: dict[str, str] = {}
    for key, value in parsed.items():
        key_text = str(key or "").strip()
        value_text = str(value or "").strip()
        if key_text and value_text:
            normalized[key_text] = value_text
    return normalized


def _normalize_defaults_payload(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BadRequestError(f"Invalid defaults JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise BadRequestError("Defaults must be a JSON object")
    normalized: dict[str, str] = {}
    for key, value in parsed.items():
        key_text = str(key or "").strip()
        if not key_text or value is None:
            continue
        normalized[key_text] = str(value).strip()
    return normalized


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    lowered = str(value).strip().lower()
    if not lowered:
        return default
    return lowered in {"1", "true", "yes", "oui", "y", "on"}


def _pick_csv_dialect(content_sample: str) -> csv.Dialect:
    sample = content_sample[:4096]
    if not sample.strip():
        raise BadRequestError("CSV file is empty")
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def _extract_row_value(
    *,
    row: dict[str, str],
    mapping: dict[str, str],
    defaults: dict[str, str],
    key: str,
) -> str | None:
    mapped_column = mapping.get(key)
    if mapped_column:
        for col_name, col_value in row.items():
            if str(col_name or "").strip() == mapped_column:
                text_value = str(col_value or "").strip()
                if text_value:
                    return text_value
    default_value = defaults.get(key)
    if default_value is not None:
        clean_default = str(default_value).strip()
        return clean_default or None
    return None


def _apply_filters(query, filters: LeadFilters, org_id: uuid.UUID):
    query = query.where(Lead.organization_id == org_id)
    if filters.extraction_job_id:
        query = query.where(Lead.extraction_job_id == filters.extraction_job_id)
    if filters.min_score is not None:
        query = query.where(Lead.quality_score >= filters.min_score)
    if filters.max_score is not None:
        query = query.where(Lead.quality_score <= filters.max_score)
    if filters.sector:
        query = query.where(Lead.sector.ilike(f"%{filters.sector}%"))
    if filters.city:
        query = query.where(Lead.city.ilike(f"%{filters.city}%"))
    if filters.department:
        query = query.where(Lead.department == filters.department)
    if filters.region:
        query = query.where(Lead.region.ilike(f"%{filters.region}%"))
    if filters.source:
        query = query.where(Lead.source == filters.source)
    if filters.lead_kind:
        query = query.where(Lead.lead_kind == filters.lead_kind)
    if filters.has_email is not None:
        query = query.where(Lead.emails.any() if filters.has_email else ~Lead.emails.any())
    if filters.has_phone is not None:
        query = query.where(Lead.phones.any() if filters.has_phone else ~Lead.phones.any())
    if filters.is_duplicate is not None:
        query = query.where(Lead.is_duplicate == filters.is_duplicate)
    if filters.consent_granted_only:
        query = query.where(Lead.consent.has(LeadConsent.consent_status == "granted"))
    if filters.date_from:
        query = query.where(Lead.created_at >= filters.date_from)
    if filters.date_to:
        query = query.where(Lead.created_at <= filters.date_to)
    if filters.search:
        query = query.where(Lead.company_name.ilike(f"%{filters.search}%"))
    return query


async def _get_lead_in_org(db: AsyncSession, lead_id: uuid.UUID, org_id: uuid.UUID) -> Lead:
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.organization_id == org_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise NotFoundError("Lead not found")
    return lead


async def _get_or_create_consent(db: AsyncSession, lead: Lead) -> LeadConsent:
    result = await db.execute(select(LeadConsent).where(LeadConsent.lead_id == lead.id))
    consent = result.scalar_one_or_none()
    if consent:
        return consent

    consent = LeadConsent(lead_id=lead.id, organization_id=lead.organization_id)
    db.add(consent)
    await db.flush()
    return consent


async def _build_consent_response(db: AsyncSession, consent_id: uuid.UUID) -> LeadConsentResponse:
    result = await db.execute(
        select(
            LeadConsent.id,
            LeadConsent.lead_id,
            LeadConsent.organization_id,
            LeadConsent.consent_status,
            LeadConsent.consent_scope,
            LeadConsent.consent_source,
            LeadConsent.consent_at,
            LeadConsent.consent_text_version,
            LeadConsent.consent_proof_ref,
            LeadConsent.privacy_policy_version,
            LeadConsent.lawful_basis,
            LeadConsent.source_campaign,
            LeadConsent.source_channel,
            LeadConsent.ip_hash,
            LeadConsent.user_agent_hash,
            LeadConsent.double_opt_in,
            LeadConsent.double_opt_in_at,
            LeadConsent.purpose,
            LeadConsent.data_retention_until,
            LeadConsent.created_at,
            LeadConsent.updated_at,
        ).where(LeadConsent.id == consent_id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundError("Lead consent not found")

    return LeadConsentResponse(
        id=row.id,
        lead_id=row.lead_id,
        organization_id=row.organization_id,
        consent_status=row.consent_status,
        consent_scope=row.consent_scope,
        consent_source=row.consent_source,
        consent_at=row.consent_at,
        consent_text_version=row.consent_text_version,
        consent_proof_ref=row.consent_proof_ref,
        privacy_policy_version=row.privacy_policy_version,
        lawful_basis=row.lawful_basis,
        source_campaign=row.source_campaign,
        source_channel=row.source_channel,
        ip_hash=row.ip_hash,
        user_agent_hash=row.user_agent_hash,
        double_opt_in=row.double_opt_in,
        double_opt_in_at=row.double_opt_in_at,
        purpose=row.purpose,
        data_retention_until=row.data_retention_until,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _require_permission(
    db: AsyncSession,
    current_user: User,
    permission: str,
) -> None:
    await PermissionService(db).require_user_permission(current_user, permission)


@router.get("", response_model=PaginatedResponse[LeadResponse])
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    extraction_job_id: uuid.UUID | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    sector: str | None = None,
    city: str | None = None,
    department: str | None = None,
    region: str | None = None,
    source: str | None = None,
    lead_kind: Literal["b2b", "b2c"] | None = None,
    is_duplicate: bool | None = None,
    consent_granted_only: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    ordering: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.view")
    if ordering:
        sort_order = "desc" if ordering.startswith("-") else "asc"
        sort_by = ordering.lstrip("-")

    filters = LeadFilters(
        extraction_job_id=extraction_job_id,
        min_score=min_score,
        max_score=max_score,
        sector=sector,
        city=city,
        department=department,
        region=region,
        source=source,
        lead_kind=lead_kind,
        is_duplicate=is_duplicate,
        consent_granted_only=consent_granted_only,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )

    base_query = select(Lead).options(
        selectinload(Lead.emails),
        selectinload(Lead.phones),
        selectinload(Lead.consent),
    )
    base_query = _apply_filters(base_query, filters, current_user.organization_id)

    # Count
    count_query = select(func.count()).select_from(
        _apply_filters(select(Lead), filters, current_user.organization_id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Sort
    sort_col = ALLOWED_LEAD_SORT_COLUMNS.get(sort_by, Lead.created_at)
    if sort_order == "desc":
        base_query = base_query.order_by(sort_col.desc(), Lead.created_at.desc())
    else:
        base_query = base_query.order_by(sort_col.asc(), Lead.created_at.desc())

    # Paginate
    offset = (page - 1) * page_size
    result = await db.execute(base_query.offset(offset).limit(page_size))
    leads = result.scalars().unique().all()

    return PaginatedResponse(
        items=[LeadResponse.model_validate(lead_item) for lead_item in leads],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/export/csv")
async def export_leads_csv(
    extraction_job_id: uuid.UUID | None = None,
    min_score: int | None = None,
    sector: str | None = None,
    city: str | None = None,
    lead_kind: Literal["b2b", "b2c"] | None = None,
    consent_granted_only: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.export")
    filters = LeadFilters(
        extraction_job_id=extraction_job_id,
        min_score=min_score,
        sector=sector,
        city=city,
        lead_kind=lead_kind,
        consent_granted_only=consent_granted_only,
    )
    query = select(Lead).options(selectinload(Lead.emails), selectinload(Lead.phones))
    query = _apply_filters(query, filters, current_user.organization_id)
    if settings.consent_enforcement_enabled:
        now_utc = datetime.now(timezone.utc)
        query = query.join(LeadConsent, LeadConsent.lead_id == Lead.id).where(
            LeadConsent.consent_status == "granted",
            LeadConsent.lawful_basis == "consent",
            or_(
                LeadConsent.data_retention_until.is_(None),
                LeadConsent.data_retention_until > now_utc,
            ),
        )
    query = query.order_by(Lead.quality_score.desc()).limit(10000)

    result = await db.execute(query)
    leads = result.scalars().unique().all()
    if settings.consent_enforcement_enabled and not leads:
        raise BadRequestError("No leads are exportable: missing or invalid consent")

    await AuditLogService(db).log(
        action="lead.export_csv",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="lead",
        details={
            "filters": {
                "min_score": min_score,
                "extraction_job_id": str(extraction_job_id) if extraction_job_id else None,
                "sector": sector,
                "city": city,
                "lead_kind": lead_kind,
                "consent_granted_only": consent_granted_only,
            },
            "count": len(leads),
            "consent_enforced": settings.consent_enforcement_enabled,
        },
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Entreprise",
            "Secteur",
            "Email",
            "Téléphone",
            "Ville",
            "Code Postal",
            "Score",
            "Source",
            "Site Web",
            "SIREN",
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
                _sanitize_csv_cell(lead.company_name),
                _sanitize_csv_cell(lead.sector),
                _sanitize_csv_cell(primary_email),
                _sanitize_csv_cell(primary_phone),
                _sanitize_csv_cell(lead.city),
                _sanitize_csv_cell(lead.postal_code),
                lead.quality_score,
                _sanitize_csv_cell(lead.source),
                _sanitize_csv_cell(lead.website),
                _sanitize_csv_cell(lead.siren),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=leads_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            )
        },
    )


@router.get("/export/xlsx")
async def export_leads_xlsx(
    extraction_job_id: uuid.UUID | None = None,
    min_score: int | None = None,
    sector: str | None = None,
    city: str | None = None,
    lead_kind: Literal["b2b", "b2c"] | None = None,
    consent_granted_only: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.export")
    filters = LeadFilters(
        extraction_job_id=extraction_job_id,
        min_score=min_score,
        sector=sector,
        city=city,
        lead_kind=lead_kind,
        consent_granted_only=consent_granted_only,
    )
    query = select(Lead).options(selectinload(Lead.emails), selectinload(Lead.phones))
    query = _apply_filters(query, filters, current_user.organization_id)
    if settings.consent_enforcement_enabled:
        now_utc = datetime.now(timezone.utc)
        query = query.join(LeadConsent, LeadConsent.lead_id == Lead.id).where(
            LeadConsent.consent_status == "granted",
            LeadConsent.lawful_basis == "consent",
            or_(
                LeadConsent.data_retention_until.is_(None),
                LeadConsent.data_retention_until > now_utc,
            ),
        )
    query = query.order_by(Lead.quality_score.desc()).limit(10000)

    result = await db.execute(query)
    leads = result.scalars().unique().all()
    if settings.consent_enforcement_enabled and not leads:
        raise BadRequestError("No leads are exportable: missing or invalid consent")

    await AuditLogService(db).log(
        action="lead.export_xlsx",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="lead",
        details={
            "filters": {
                "min_score": min_score,
                "extraction_job_id": str(extraction_job_id) if extraction_job_id else None,
                "sector": sector,
                "city": city,
                "lead_kind": lead_kind,
                "consent_granted_only": consent_granted_only,
            },
            "count": len(leads),
            "consent_enforced": settings.consent_enforcement_enabled,
        },
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Leads"
    sheet.append(
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

        sheet.append(
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
            ]
        )

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f"attachment; filename=leads_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            )
        },
    )


@router.get("/segments/suggested", response_model=SuggestedSegmentResponse)
async def get_suggested_segments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.view")
    org_id = current_user.organization_id
    has_contact = or_(Lead.emails.any(), Lead.phones.any())

    async def _count(*conditions):
        query = select(func.count()).where(Lead.organization_id == org_id, *conditions)
        return (await db.execute(query)).scalar() or 0

    hot_b2b = await _count(
        Lead.lead_kind == "b2b",
        Lead.is_duplicate.is_(False),
        Lead.quality_score >= 80,
        has_contact,
    )
    warm_b2b = await _count(
        Lead.lead_kind == "b2b",
        Lead.is_duplicate.is_(False),
        Lead.quality_score >= 55,
        Lead.quality_score < 80,
        has_contact,
    )
    b2c_ready = await _count(
        Lead.lead_kind == "b2c",
        Lead.is_duplicate.is_(False),
        Lead.quality_score >= 55,
        has_contact,
        Lead.consent.has(LeadConsent.consent_status == "granted"),
    )
    enrich_needed = await _count(
        Lead.is_duplicate.is_(False),
        or_(
            Lead.quality_score < 55,
            ~has_contact,
        ),
    )

    items = [
        SuggestedSegment(
            code="b2b_hot",
            label="B2B Hot",
            description="Leads B2B a tres fort potentiel (score >= 80)",
            count=hot_b2b,
            filters={
                "lead_kind": "b2b",
                "min_score": 80,
                "has_email": True,
                "is_duplicate": False,
            },
        ),
        SuggestedSegment(
            code="b2b_warm",
            label="B2B Warm",
            description="Leads B2B exploitables pour nurturing (score 55-79)",
            count=warm_b2b,
            filters={
                "lead_kind": "b2b",
                "min_score": 55,
                "max_score": 79,
                "is_duplicate": False,
            },
        ),
        SuggestedSegment(
            code="b2c_ready",
            label="B2C Conforme",
            description="Leads B2C consentis et activables",
            count=b2c_ready,
            filters={
                "lead_kind": "b2c",
                "min_score": 55,
                "consent_granted_only": True,
                "is_duplicate": False,
            },
        ),
        SuggestedSegment(
            code="enrichment_needed",
            label="A Enrichir",
            description="Leads incomplets ou score faible a enrichir en priorite",
            count=enrich_needed,
            filters={
                "max_score": 54,
                "is_duplicate": False,
            },
        ),
    ]
    return SuggestedSegmentResponse(items=items)


@router.post("/b2c/intake", response_model=LeadResponse)
async def intake_b2c_lead(
    data: B2CLeadIntakeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "b2c.intake")
    if not settings.b2c_mode_enabled:
        raise BadRequestError("B2C mode is disabled on this environment")
    lead = await B2CIntakeService(db).intake_for_org(
        organization_id=current_user.organization_id,
        data=data,
        actor_user_id=current_user.id,
        action="lead.b2c_intake",
        source_context="manual_api",
    )
    return LeadResponse.model_validate(lead)


@router.post("/b2c/intake/csv", response_model=B2CCsvImportSummary)
async def intake_b2c_csv(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    defaults: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "b2c.intake")
    if not settings.b2c_mode_enabled:
        raise BadRequestError("B2C mode is disabled on this environment")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise BadRequestError("Only .csv files are supported")

    mapping_payload = _normalize_mapping_payload(mapping)
    defaults_payload = _normalize_defaults_payload(defaults)

    has_full_name_mapping = bool(mapping_payload.get("full_name"))
    has_split_name_mapping = bool(mapping_payload.get("first_name")) and bool(
        mapping_payload.get("last_name")
    )
    if not has_full_name_mapping and not has_split_name_mapping:
        raise BadRequestError("Mapping requires full_name or first_name + last_name")

    max_csv_size = 10 * 1024 * 1024  # 10 MB
    chunks = []
    total_size = 0
    while chunk := await file.read(64 * 1024):
        total_size += len(chunk)
        if total_size > max_csv_size:
            raise BadRequestError(f"CSV file too large (max {max_csv_size // (1024 * 1024)} MB)")
        chunks.append(chunk)
    content_bytes = b"".join(chunks)
    if not content_bytes:
        raise BadRequestError("CSV file is empty")

    try:
        content = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            content = content_bytes.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise BadRequestError(f"Unsupported CSV encoding: {exc}") from exc

    dialect = _pick_csv_dialect(content)
    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    if not reader.fieldnames:
        raise BadRequestError("CSV header is missing")

    total_rows = 0
    imported = 0
    duplicates = 0
    failed = 0
    errors: list[B2CCsvImportError] = []
    timestamp = datetime.now(timezone.utc)
    proof_prefix = defaults_payload.get("proof_prefix", "csv-b2c-import")
    service = B2CIntakeService(db)

    for index, row in enumerate(reader, start=2):
        total_rows += 1
        row_clean = {
            str(key or "").strip(): str(value or "").strip()
            for key, value in (row or {}).items()
            if key is not None
        }
        if not any(row_clean.values()):
            continue

        full_name = _extract_row_value(
            row=row_clean,
            mapping=mapping_payload,
            defaults=defaults_payload,
            key="full_name",
        )
        if not full_name:
            first_name = _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="first_name",
            )
            last_name = _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="last_name",
            )
            full_name = " ".join(part for part in [first_name, last_name] if part).strip()

        consent_at_raw = _extract_row_value(
            row=row_clean,
            mapping=mapping_payload,
            defaults=defaults_payload,
            key="consent_at",
        )
        consent_at = consent_at_raw or timestamp.isoformat()

        consent_proof_ref = (
            _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="consent_proof_ref",
            )
            or f"{proof_prefix}-{timestamp.strftime('%Y%m%d%H%M%S')}-{index:06d}"
        )

        payload = {
            "full_name": full_name or "",
            "email": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="email",
            ),
            "phone": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="phone",
            ),
            "city": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="city",
            ),
            "consent_source": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="consent_source",
            )
            or "crm_import",
            "consent_at": consent_at,
            "consent_text_version": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="consent_text_version",
            )
            or "v1.0",
            "consent_proof_ref": consent_proof_ref,
            "privacy_policy_version": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="privacy_policy_version",
            )
            or "pp-2026-01",
            "source_campaign": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="source_campaign",
            ),
            "source_channel": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="source_channel",
            ),
            "purpose": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="purpose",
            )
            or "prospection_commerciale",
            "double_opt_in": _parse_bool(
                _extract_row_value(
                    row=row_clean,
                    mapping=mapping_payload,
                    defaults=defaults_payload,
                    key="double_opt_in",
                ),
                default=False,
            ),
            "double_opt_in_at": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="double_opt_in_at",
            ),
            "data_retention_until": _extract_row_value(
                row=row_clean,
                mapping=mapping_payload,
                defaults=defaults_payload,
                key="data_retention_until",
            ),
        }

        try:
            validated = B2CLeadIntakeCreate.model_validate(payload)
            async with db.begin_nested():
                lead = await service.intake_for_org(
                    organization_id=current_user.organization_id,
                    data=validated,
                    actor_user_id=current_user.id,
                    action="lead.b2c_intake_csv",
                    source_context="csv_import",
                )
            imported += 1
            if bool(getattr(lead, "is_duplicate", False)):
                duplicates += 1
        except Exception as exc:
            failed += 1
            if len(errors) < 100:
                errors.append(B2CCsvImportError(row_number=index, message=str(exc)))

    await AuditLogService(db).log(
        action="lead.b2c_csv_import",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="lead",
        details={
            "filename": file.filename,
            "total_rows": total_rows,
            "imported": imported,
            "duplicates": duplicates,
            "failed": failed,
        },
    )

    return B2CCsvImportSummary(
        total_rows=total_rows,
        imported=imported,
        duplicates=duplicates,
        failed=failed,
        errors=errors,
    )


@router.get("/{lead_id}/consent", response_model=LeadConsentResponse)
async def get_lead_consent(
    lead_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.view")
    lead = await _get_lead_in_org(db, lead_id, current_user.organization_id)
    consent = await _get_or_create_consent(db, lead)
    return await _build_consent_response(db, consent.id)


@router.patch("/{lead_id}/consent", response_model=LeadConsentResponse)
async def update_lead_consent(
    lead_id: uuid.UUID,
    data: LeadConsentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "b2c.consent.manage")
    lead = await _get_lead_in_org(db, lead_id, current_user.organization_id)
    consent = await _get_or_create_consent(db, lead)
    old_state = {
        "consent_status": consent.consent_status,
        "consent_scope": consent.consent_scope,
        "lawful_basis": consent.lawful_basis,
        "double_opt_in": consent.double_opt_in,
    }

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(consent, field, value)

    if consent.double_opt_in is False:
        consent.double_opt_in_at = None
    if consent.consent_status in {"granted", "denied", "revoked"} and consent.consent_at is None:
        consent.consent_at = datetime.now(timezone.utc)

    await db.flush()
    await AuditLogService(db).log(
        action="lead.consent_update",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="lead_consent",
        resource_id=str(consent.id),
        details={
            "lead_id": str(lead.id),
            "old_state": old_state,
            "new_state": {
                "consent_status": consent.consent_status,
                "consent_scope": consent.consent_scope,
                "lawful_basis": consent.lawful_basis,
                "double_opt_in": consent.double_opt_in,
            },
        },
    )
    return await _build_consent_response(db, consent.id)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.view")
    result = await db.execute(
        select(Lead)
        .options(selectinload(Lead.emails), selectinload(Lead.phones), selectinload(Lead.consent))
        .where(Lead.id == lead_id, Lead.organization_id == current_user.organization_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise NotFoundError("Lead not found")
    return LeadResponse.model_validate(lead)


@router.get("/{lead_id}/score-breakdown")
async def get_lead_score_breakdown(
    lead_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.view")
    result = await db.execute(
        select(Lead)
        .options(selectinload(Lead.emails), selectinload(Lead.phones))
        .where(Lead.id == lead_id, Lead.organization_id == current_user.organization_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise NotFoundError("Lead not found")

    scoring = ScoringService(db)
    profile = await scoring.get_profile_config(lead.organization_id)
    breakdown = scoring.calculate_score_breakdown(lead, profile.weights)
    return {
        "lead_id": str(lead.id),
        "stored_score": lead.quality_score,
        "computed_score": breakdown["score"],
        "raw_total": breakdown["raw_total"],
        "high_threshold": profile.high_threshold,
        "medium_threshold": profile.medium_threshold,
        "items": breakdown["items"],
    }


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    data: LeadUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.manage")
    result = await db.execute(
        select(Lead)
        .options(selectinload(Lead.emails), selectinload(Lead.phones), selectinload(Lead.consent))
        .where(Lead.id == lead_id, Lead.organization_id == current_user.organization_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise NotFoundError("Lead not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)

    await db.flush()
    return LeadResponse.model_validate(lead)


@router.delete("/{lead_id}", response_model=MessageResponse)
async def delete_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.manage")
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.organization_id == current_user.organization_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise NotFoundError("Lead not found")

    lead_id_str = str(lead.id)
    lead_company_name = lead.company_name
    await db.delete(lead)
    await db.flush()
    await AuditLogService(db).log(
        action="lead.delete",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="lead",
        resource_id=lead_id_str,
        details={"company_name": lead_company_name},
    )
    return MessageResponse(message="Lead deleted")


@router.post("/deduplicate", response_model=MessageResponse)
async def deduplicate_leads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_permission(db, current_user, "leads.manage")
    from app.services.cleaning_service import CleaningService

    service = CleaningService(db)
    count = await service.deduplicate(current_user.organization_id)
    await AuditLogService(db).log(
        action="lead.deduplicate",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="lead",
        details={"duplicates_marked": count},
    )
    return MessageResponse(message=f"{count} duplicates marked")
