import csv
import io
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _sanitize_csv_cell(value: str | None) -> str:
        if value is None:
            return ""
        text = str(value)
        if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{text}"
        return text

    async def export_csv(self, org_id: uuid.UUID, filters: dict | None = None) -> str:
        """Generate CSV content for leads matching filters."""
        query = (
            select(Lead)
            .options(selectinload(Lead.emails), selectinload(Lead.phones))
            .where(Lead.organization_id == org_id, Lead.is_duplicate.is_(False))
            .order_by(Lead.quality_score.desc())
            .limit(10000)
        )

        if filters:
            if filters.get("min_score"):
                query = query.where(Lead.quality_score >= filters["min_score"])
            if filters.get("sector"):
                query = query.where(Lead.sector.ilike(f"%{filters['sector']}%"))
            if filters.get("city"):
                query = query.where(Lead.city.ilike(f"%{filters['city']}%"))

        result = await self.db.execute(query)
        leads = result.scalars().unique().all()

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
                "Département",
                "Score",
                "Source",
                "Site Web",
                "SIREN",
            ]
        )

        for lead in leads:
            primary_email = ""
            for e in lead.emails:
                if e.is_primary:
                    primary_email = e.email
                    break
            if not primary_email and lead.emails:
                primary_email = lead.emails[0].email

            primary_phone = ""
            for p in lead.phones:
                if p.is_primary:
                    primary_phone = p.phone_normalized or p.phone_raw or ""
                    break
            if not primary_phone and lead.phones:
                primary_phone = lead.phones[0].phone_normalized or lead.phones[0].phone_raw or ""

            writer.writerow(
                [
                    self._sanitize_csv_cell(lead.company_name),
                    self._sanitize_csv_cell(lead.sector),
                    self._sanitize_csv_cell(primary_email),
                    self._sanitize_csv_cell(primary_phone),
                    self._sanitize_csv_cell(lead.city),
                    self._sanitize_csv_cell(lead.postal_code),
                    self._sanitize_csv_cell(lead.department),
                    lead.quality_score,
                    self._sanitize_csv_cell(lead.source),
                    self._sanitize_csv_cell(lead.website),
                    self._sanitize_csv_cell(lead.siren),
                ]
            )

        return output.getvalue()
