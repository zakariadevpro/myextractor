from sqlalchemy import func, select
from sqlalchemy.orm import Session

from winxtract.storage.db import LeadORM


def compute_quality_report(session: Session, source_slug: str | None = None) -> dict:
    base_stmt = select(LeadORM)
    if source_slug:
        base_stmt = base_stmt.where(LeadORM.source_slug == source_slug)

    total = session.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
    if total == 0:
        return {
            "total_leads": 0,
            "with_email": 0,
            "with_phone": 0,
            "with_website": 0,
            "with_city": 0,
            "avg_score": 0.0,
            "coverage": {
                "email_ratio": 0.0,
                "phone_ratio": 0.0,
                "website_ratio": 0.0,
                "city_ratio": 0.0,
            },
            "top_cities": [],
            "by_source": [],
        }

    with_email = session.scalar(
        select(func.count()).select_from(
            base_stmt.where((LeadORM.emails.is_not(None)) & (LeadORM.emails != "")).subquery()
        )
    ) or 0
    with_phone = session.scalar(
        select(func.count()).select_from(
            base_stmt.where((LeadORM.phones.is_not(None)) & (LeadORM.phones != "")).subquery()
        )
    ) or 0
    with_website = session.scalar(
        select(func.count()).select_from(
            base_stmt.where((LeadORM.website.is_not(None)) & (LeadORM.website != "")).subquery()
        )
    ) or 0
    with_city = session.scalar(
        select(func.count()).select_from(
            base_stmt.where((LeadORM.city.is_not(None)) & (LeadORM.city != "")).subquery()
        )
    ) or 0
    avg_sub = base_stmt.subquery()
    avg_score = float(session.scalar(select(func.avg(avg_sub.c.score)).select_from(avg_sub)) or 0.0)

    city_stmt = (
        select(LeadORM.city, func.count().label("cnt"))
        .where((LeadORM.city.is_not(None)) & (LeadORM.city != ""))
        .group_by(LeadORM.city)
        .order_by(func.count().desc())
        .limit(10)
    )
    if source_slug:
        city_stmt = city_stmt.where(LeadORM.source_slug == source_slug)
    top_cities = [{"city": city or "", "count": int(cnt)} for city, cnt in session.execute(city_stmt).all()]

    by_source_stmt = (
        select(LeadORM.source_slug, func.count().label("cnt"), func.avg(LeadORM.score).label("avg_score"))
        .group_by(LeadORM.source_slug)
        .order_by(func.count().desc())
    )
    if source_slug:
        by_source_stmt = by_source_stmt.where(LeadORM.source_slug == source_slug)
    by_source = [
        {"source_slug": slug, "count": int(cnt), "avg_score": float(avg or 0.0)}
        for slug, cnt, avg in session.execute(by_source_stmt).all()
    ]

    return {
        "total_leads": int(total),
        "with_email": int(with_email),
        "with_phone": int(with_phone),
        "with_website": int(with_website),
        "with_city": int(with_city),
        "avg_score": round(avg_score, 2),
        "coverage": {
            "email_ratio": round(with_email / total, 4),
            "phone_ratio": round(with_phone / total, 4),
            "website_ratio": round(with_website / total, 4),
            "city_ratio": round(with_city / total, 4),
        },
        "top_cities": top_cities,
        "by_source": by_source,
    }
