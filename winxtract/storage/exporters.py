import csv
import json
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from winxtract.storage.db import LeadORM

EXPORT_FIELDS = [
    "id",
    "source_slug",
    "name",
    "city",
    "website",
    "emails",
    "phones",
    "score",
    "page_url",
    "scraped_at",
]


def _query_leads(
    min_score: int,
    source_slug: str | None,
    *,
    source_slugs: list[str] | None = None,
    city: str | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    scraped_from: datetime | None = None,
    scraped_to: datetime | None = None,
    name_contains: str | None = None,
) -> Select:
    stmt = select(LeadORM).where(LeadORM.score >= min_score)
    if source_slug:
        stmt = stmt.where(LeadORM.source_slug == source_slug)
    elif source_slugs:
        cleaned = [slug.strip() for slug in source_slugs if slug and slug.strip()]
        if cleaned:
            stmt = stmt.where(LeadORM.source_slug.in_(cleaned))
    normalized_city = city.strip().lower() if city else ""
    if normalized_city:
        stmt = stmt.where(func.lower(LeadORM.city) == normalized_city)
    if has_email is True:
        stmt = stmt.where(and_(LeadORM.emails.is_not(None), LeadORM.emails != ""))
    elif has_email is False:
        stmt = stmt.where((LeadORM.emails.is_(None)) | (LeadORM.emails == ""))
    if has_phone is True:
        stmt = stmt.where(and_(LeadORM.phones.is_not(None), LeadORM.phones != ""))
    elif has_phone is False:
        stmt = stmt.where((LeadORM.phones.is_(None)) | (LeadORM.phones == ""))
    if scraped_from:
        stmt = stmt.where(LeadORM.scraped_at >= scraped_from)
    if scraped_to:
        stmt = stmt.where(LeadORM.scraped_at <= scraped_to)
    if name_contains:
        stmt = stmt.where(LeadORM.name.ilike(f"%{name_contains.strip()}%"))
    return stmt.order_by(LeadORM.score.desc(), LeadORM.scraped_at.desc())


def export_leads(
    session: Session,
    *,
    output: str,
    fmt: str,
    min_score: int = 0,
    source_slug: str | None = None,
    source_slugs: list[str] | None = None,
    city: str | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    scraped_from: datetime | None = None,
    scraped_to: datetime | None = None,
    name_contains: str | None = None,
) -> int:
    rows = session.scalars(
        _query_leads(
            min_score=min_score,
            source_slug=source_slug,
            source_slugs=source_slugs,
            city=city,
            has_email=has_email,
            has_phone=has_phone,
            scraped_from=scraped_from,
            scraped_to=scraped_to,
            name_contains=name_contains,
        )
    ).all()
    data = [
        {
            "id": row.id,
            "source_slug": row.source_slug,
            "name": row.name,
            "city": row.city,
            "website": row.website,
            "emails": row.emails,
            "phones": row.phones,
            "score": row.score,
            "page_url": row.page_url,
            "scraped_at": row.scraped_at.isoformat() if row.scraped_at else None,
        }
        for row in rows
    ]
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        _write_csv(path, data)
    elif fmt == "json":
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "xlsx":
        _write_xlsx(path, data)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")
    return len(data)


def _write_csv(path: Path, data: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        if data:
            writer.writerows([{field: row.get(field) for field in EXPORT_FIELDS} for row in data])


def _write_xlsx(path: Path, data: list[dict]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "leads"
    ws.append(EXPORT_FIELDS)
    for row in data:
        ws.append([row.get(col) for col in EXPORT_FIELDS])
    wb.save(path)
