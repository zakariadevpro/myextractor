import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select
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
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Leads today
        leads_today_q = select(func.count()).where(
            Lead.organization_id == org_id, Lead.created_at >= today
        )
        leads_today = (await self.db.execute(leads_today_q)).scalar() or 0

        # Total leads
        total_q = select(func.count()).where(Lead.organization_id == org_id)
        total = (await self.db.execute(total_q)).scalar() or 0

        # Average score
        avg_q = select(func.avg(Lead.quality_score)).where(
            Lead.organization_id == org_id, Lead.quality_score > 0
        )
        avg_score = (await self.db.execute(avg_q)).scalar() or 0.0

        # Email valid rate
        email_total_q = (
            select(func.count())
            .select_from(LeadEmail)
            .join(Lead)
            .where(Lead.organization_id == org_id, LeadEmail.is_valid.isnot(None))
        )
        email_total = (await self.db.execute(email_total_q)).scalar() or 0

        email_valid_q = (
            select(func.count())
            .select_from(LeadEmail)
            .join(Lead)
            .where(Lead.organization_id == org_id, LeadEmail.is_valid)
        )
        email_valid = (await self.db.execute(email_valid_q)).scalar() or 0
        email_rate = (email_valid / email_total * 100) if email_total > 0 else 0.0

        # Duplicate rate
        dup_q = select(func.count()).where(
            Lead.organization_id == org_id, Lead.is_duplicate
        )
        dup_count = (await self.db.execute(dup_q)).scalar() or 0
        dup_rate = (dup_count / total * 100) if total > 0 else 0.0

        # Active extractions
        active_q = select(func.count()).where(
            ExtractionJob.organization_id == org_id,
            ExtractionJob.status.in_(["pending", "running"]),
        )
        active = (await self.db.execute(active_q)).scalar() or 0

        return DashboardOverview(
            leads_today=leads_today,
            leads_total=total,
            avg_score=round(float(avg_score), 1),
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
        now_utc = datetime.now(timezone.utc)
        retention_warn = now_utc + timedelta(days=7)

        total_b2c_q = select(func.count()).where(
            Lead.organization_id == org_id,
            Lead.lead_kind == "b2c",
        )
        total_b2c = (await self.db.execute(total_b2c_q)).scalar() or 0

        def _status_count(status: str):
            return (
                select(func.count())
                .select_from(Lead)
                .join(LeadConsent, LeadConsent.lead_id == Lead.id)
                .where(
                    Lead.organization_id == org_id,
                    Lead.lead_kind == "b2c",
                    LeadConsent.consent_status == status,
                )
            )

        granted = (await self.db.execute(_status_count("granted"))).scalar() or 0
        denied = (await self.db.execute(_status_count("denied"))).scalar() or 0
        revoked = (await self.db.execute(_status_count("revoked"))).scalar() or 0
        unknown = max(total_b2c - granted - denied - revoked, 0)

        exportable_q = (
            select(func.count())
            .select_from(Lead)
            .join(LeadConsent, LeadConsent.lead_id == Lead.id)
            .where(
                Lead.organization_id == org_id,
                Lead.lead_kind == "b2c",
                LeadConsent.consent_status == "granted",
                LeadConsent.lawful_basis == "consent",
                or_(
                    LeadConsent.data_retention_until.is_(None),
                    LeadConsent.data_retention_until > now_utc,
                ),
            )
        )
        exportable = (await self.db.execute(exportable_q)).scalar() or 0

        expiring_q = (
            select(func.count())
            .select_from(Lead)
            .join(LeadConsent, LeadConsent.lead_id == Lead.id)
            .where(
                Lead.organization_id == org_id,
                Lead.lead_kind == "b2c",
                LeadConsent.consent_status == "granted",
                LeadConsent.data_retention_until.is_not(None),
                LeadConsent.data_retention_until >= now_utc,
                LeadConsent.data_retention_until <= retention_warn,
            )
        )
        expiring_7d = (await self.db.execute(expiring_q)).scalar() or 0

        doi_q = (
            select(func.count())
            .select_from(Lead)
            .join(LeadConsent, LeadConsent.lead_id == Lead.id)
            .where(
                Lead.organization_id == org_id,
                Lead.lead_kind == "b2c",
                LeadConsent.consent_status == "granted",
                LeadConsent.double_opt_in,
            )
        )
        doi_count = (await self.db.execute(doi_q)).scalar() or 0
        doi_rate = (doi_count / granted * 100) if granted > 0 else 0.0
        revocation_rate = (revoked / total_b2c * 100) if total_b2c > 0 else 0.0

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
            exportable_contacts=exportable,
            expiring_7d=expiring_7d,
            double_opt_in_rate=round(doi_rate, 1),
            revocation_rate=round(revocation_rate, 1),
            by_source=[
                B2CConsentSourceStat(source=row.source, count=row.count)
                for row in by_source_rows
            ],
        )

    async def get_lead_intelligence_overview(self, org_id: uuid.UUID) -> LeadIntelligenceOverview:
        scoring_profile = await ScoringService(self.db).get_profile_config(org_id)
        high_threshold = scoring_profile.high_threshold
        medium_threshold = scoring_profile.medium_threshold
        base_filter = Lead.organization_id == org_id

        total_q = select(func.count()).where(base_filter)
        total_leads = (await self.db.execute(total_q)).scalar() or 0

        ready_q = select(func.count()).where(
            base_filter,
            Lead.is_duplicate.is_(False),
            or_(Lead.emails.any(), Lead.phones.any()),
        )
        ready_to_contact = (await self.db.execute(ready_q)).scalar() or 0
        missing_contact = max(total_leads - ready_to_contact, 0)

        high_q = select(func.count()).where(base_filter, Lead.quality_score >= high_threshold)
        medium_q = select(func.count()).where(
            base_filter,
            Lead.quality_score >= medium_threshold,
            Lead.quality_score < high_threshold,
        )
        low_q = select(func.count()).where(base_filter, Lead.quality_score < medium_threshold)
        high_potential = (await self.db.execute(high_q)).scalar() or 0
        medium_potential = (await self.db.execute(medium_q)).scalar() or 0
        low_potential = (await self.db.execute(low_q)).scalar() or 0

        priority_bucket = case(
            (Lead.quality_score >= high_threshold, "hot"),
            (Lead.quality_score >= medium_threshold, "warm"),
            else_="cold",
        ).label("bucket")
        buckets_q = (
            select(priority_bucket, func.count().label("count"))
            .where(base_filter)
            .group_by(priority_bucket)
        )
        bucket_rows = (await self.db.execute(buckets_q)).all()
        bucket_map = {"hot": 0, "warm": 0, "cold": 0}
        for row in bucket_rows:
            bucket_map[str(row.bucket)] = row.count

        by_source_q = (
            select(Lead.source, func.count().label("count"))
            .where(base_filter)
            .group_by(Lead.source)
            .order_by(func.count().desc())
            .limit(8)
        )
        by_source_rows = (await self.db.execute(by_source_q)).all()

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
            missing_contact=missing_contact,
            high_potential=high_potential,
            medium_potential=medium_potential,
            low_potential=low_potential,
            priority_buckets=[
                LeadPriorityStat(bucket="hot", count=bucket_map["hot"]),
                LeadPriorityStat(bucket="warm", count=bucket_map["warm"]),
                LeadPriorityStat(bucket="cold", count=bucket_map["cold"]),
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
