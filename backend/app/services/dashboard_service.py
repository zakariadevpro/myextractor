import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, literal_column, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import ExtractionJob
from app.models.lead import Lead, LeadEmail
from app.models.lead_consent import LeadConsent
from app.schemas.dashboard import (
    B2CComplianceOverview,
    B2CConsentSourceStat,
    DashboardOverview,
    LeadIntelligenceOverview,
    LeadKindStat,
    LeadPriorityStat,
    LeadSourceStat,
    SectorStat,
    ZoneStat,
)
from app.services.scoring_service import ScoringService


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_overview(self, org_id: uuid.UUID) -> DashboardOverview:
        """Consolidated: 7 queries → 2 queries."""
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Query 1: all lead-level metrics in one pass
        leads_q = select(
            func.count().label("total"),
            func.count().filter(Lead.created_at >= today).label("leads_today"),
            func.coalesce(
                func.avg(Lead.quality_score).filter(Lead.quality_score > 0), 0
            ).label("avg_score"),
            func.count().filter(Lead.is_duplicate).label("dup_count"),
        ).where(Lead.organization_id == org_id)

        row = (await self.db.execute(leads_q)).one()
        total = row.total or 0
        dup_rate = (row.dup_count / total * 100) if total > 0 else 0.0

        # Query 2: email valid rate (requires join)
        email_q = select(
            func.count().filter(LeadEmail.is_valid.isnot(None)).label("email_total"),
            func.count().filter(LeadEmail.is_valid).label("email_valid"),
        ).select_from(LeadEmail).join(Lead).where(Lead.organization_id == org_id)

        email_row = (await self.db.execute(email_q)).one()
        email_total = email_row.email_total or 0
        email_valid = email_row.email_valid or 0
        email_rate = (email_valid / email_total * 100) if email_total > 0 else 0.0

        # Query 3: active extractions (different table)
        active_q = select(func.count()).where(
            ExtractionJob.organization_id == org_id,
            ExtractionJob.status.in_(["pending", "running"]),
        )
        active = (await self.db.execute(active_q)).scalar() or 0

        return DashboardOverview(
            leads_today=row.leads_today or 0,
            leads_total=total,
            avg_score=round(float(row.avg_score), 1),
            email_valid_rate=round(email_rate, 1),
            duplicate_rate=round(dup_rate, 1),
            active_extractions=active,
        )

    async def get_leads_by_sector(self, org_id: uuid.UUID) -> list[SectorStat]:
        result = await self.db.execute(
            select(Lead.sector, func.count().label("count"))
            .where(Lead.organization_id == org_id, Lead.sector.isnot(None))
            .group_by(Lead.sector)
            .order_by(func.count().desc())
            .limit(10)
        )
        return [SectorStat(sector=row.sector, count=row.count) for row in result.all()]

    async def get_leads_by_zone(self, org_id: uuid.UUID) -> list[ZoneStat]:
        result = await self.db.execute(
            select(Lead.department, func.count().label("count"))
            .where(Lead.organization_id == org_id, Lead.department.isnot(None))
            .group_by(Lead.department)
            .order_by(func.count().desc())
            .limit(15)
        )
        return [ZoneStat(zone=row.department, count=row.count) for row in result.all()]

    async def get_b2c_compliance_overview(self, org_id: uuid.UUID) -> B2CComplianceOverview:
        """Consolidated: 9 queries → 2 queries."""
        now_utc = datetime.now(timezone.utc)
        retention_warn = now_utc + timedelta(days=7)

        # Query 1: all consent metrics in one pass via LEFT JOIN + conditional aggregation
        metrics_q = (
            select(
                func.count().label("total_b2c"),
                func.count().filter(LeadConsent.consent_status == "granted").label("granted"),
                func.count().filter(LeadConsent.consent_status == "denied").label("denied"),
                func.count().filter(LeadConsent.consent_status == "revoked").label("revoked"),
                func.count().filter(
                    LeadConsent.consent_status == "granted",
                    LeadConsent.lawful_basis == "consent",
                    or_(
                        LeadConsent.data_retention_until.is_(None),
                        LeadConsent.data_retention_until > now_utc,
                    ),
                ).label("exportable"),
                func.count().filter(
                    LeadConsent.consent_status == "granted",
                    LeadConsent.data_retention_until.is_not(None),
                    LeadConsent.data_retention_until >= now_utc,
                    LeadConsent.data_retention_until <= retention_warn,
                ).label("expiring_7d"),
                func.count().filter(
                    LeadConsent.consent_status == "granted",
                    LeadConsent.double_opt_in,
                ).label("doi_count"),
            )
            .select_from(Lead)
            .join(LeadConsent, LeadConsent.lead_id == Lead.id, isouter=True)
            .where(Lead.organization_id == org_id, Lead.lead_kind == "b2c")
        )

        row = (await self.db.execute(metrics_q)).one()
        total_b2c = row.total_b2c or 0
        granted = row.granted or 0
        denied = row.denied or 0
        revoked = row.revoked or 0
        unknown = max(total_b2c - granted - denied - revoked, 0)
        doi_rate = (row.doi_count / granted * 100) if granted > 0 else 0.0
        revocation_rate = (revoked / total_b2c * 100) if total_b2c > 0 else 0.0

        # Query 2: by_source aggregation
        source_expr = func.coalesce(LeadConsent.consent_source, "unknown")
        by_source_q = (
            select(
                source_expr.label("source"),
                func.count().label("count"),
            )
            .select_from(Lead)
            .join(LeadConsent, LeadConsent.lead_id == Lead.id, isouter=True)
            .where(Lead.organization_id == org_id, Lead.lead_kind == "b2c")
            .group_by(source_expr)
            .order_by(func.count().desc())
            .limit(10)
        )
        by_source_rows = (await self.db.execute(by_source_q)).all()

        return B2CComplianceOverview(
            total_b2c=total_b2c,
            consent_granted=granted,
            consent_denied=denied,
            consent_revoked=revoked,
            consent_unknown=unknown,
            exportable_contacts=row.exportable or 0,
            expiring_7d=row.expiring_7d or 0,
            double_opt_in_rate=round(doi_rate, 1),
            revocation_rate=round(revocation_rate, 1),
            by_source=[
                B2CConsentSourceStat(source=row.source, count=row.count) for row in by_source_rows
            ],
        )

    async def get_lead_intelligence_overview(self, org_id: uuid.UUID) -> LeadIntelligenceOverview:
        """Consolidated: 8 queries → 3 queries."""
        scoring_profile = await ScoringService(self.db).get_profile_config(org_id)
        high_threshold = scoring_profile.high_threshold
        medium_threshold = scoring_profile.medium_threshold
        base_filter = Lead.organization_id == org_id

        # Query 1: all counts + buckets in one pass
        stats_q = select(
            func.count().label("total"),
            func.count().filter(
                Lead.is_duplicate.is_(False),
                or_(Lead.emails.any(), Lead.phones.any()),
            ).label("ready_to_contact"),
            func.count().filter(Lead.quality_score >= high_threshold).label("high"),
            func.count().filter(
                Lead.quality_score >= medium_threshold,
                Lead.quality_score < high_threshold,
            ).label("medium"),
            func.count().filter(Lead.quality_score < medium_threshold).label("low"),
        ).where(base_filter)

        row = (await self.db.execute(stats_q)).one()
        total_leads = row.total or 0
        ready_to_contact = row.ready_to_contact or 0

        # Query 2: by source
        by_source_q = (
            select(Lead.source, func.count().label("count"))
            .where(base_filter)
            .group_by(Lead.source)
            .order_by(func.count().desc())
            .limit(8)
        )
        by_source_rows = (await self.db.execute(by_source_q)).all()

        # Query 3: by kind
        by_kind_q = (
            select(Lead.lead_kind, func.count().label("count"))
            .where(base_filter)
            .group_by(Lead.lead_kind)
            .order_by(func.count().desc())
        )
        by_kind_rows = (await self.db.execute(by_kind_q)).all()

        return LeadIntelligenceOverview(
            total_leads=total_leads,
            ready_to_contact=ready_to_contact,
            missing_contact=max(total_leads - ready_to_contact, 0),
            high_potential=row.high or 0,
            medium_potential=row.medium or 0,
            low_potential=row.low or 0,
            priority_buckets=[
                LeadPriorityStat(bucket="hot", count=row.high or 0),
                LeadPriorityStat(bucket="warm", count=row.medium or 0),
                LeadPriorityStat(bucket="cold", count=row.low or 0),
            ],
            by_source=[
                LeadSourceStat(source=row.source or "unknown", count=row.count)
                for row in by_source_rows
            ],
            by_kind=[
                LeadKindStat(lead_kind=row.lead_kind, count=row.count)
                for row in by_kind_rows
                if row.lead_kind in {"b2b", "b2c"}
            ],
        )
