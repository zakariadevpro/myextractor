import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadEmail, LeadPhone
from app.utils.email_validator import is_valid_email
from app.utils.phone import detect_phone_type, normalize_phone
from app.utils.text_cleaner import clean_company_name, clean_text


class CleaningService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def deduplicate(self, org_id: uuid.UUID) -> int:
        """Mark duplicates based on normalized company_name + normalized city."""
        # Recompute dedup state from scratch for consistency after each extraction batch.
        await self.db.execute(
            update(Lead).where(Lead.organization_id == org_id).values(is_duplicate=False)
        )

        result = await self.db.execute(
            select(Lead.id, Lead.company_name, Lead.city)
            .where(Lead.organization_id == org_id)
            .order_by(Lead.created_at.asc())
        )
        rows = result.all()

        first_seen_by_key: dict[tuple[str, str], uuid.UUID] = {}
        duplicate_ids: list[uuid.UUID] = []

        for lead_id, company_name, city in rows:
            key = (clean_company_name(company_name or ""), clean_text(city or "").upper())
            if not key[0]:
                continue
            if key in first_seen_by_key:
                duplicate_ids.append(lead_id)
            else:
                first_seen_by_key[key] = lead_id

        if not duplicate_ids:
            return 0

        marked = await self.db.execute(
            update(Lead).where(Lead.id.in_(duplicate_ids)).values(is_duplicate=True)
        )
        return marked.rowcount or 0

    async def validate_emails(self, org_id: uuid.UUID) -> int:
        """Validate all unvalidated emails for leads in the org."""
        result = await self.db.execute(
            select(LeadEmail)
            .join(Lead)
            .where(Lead.organization_id == org_id, LeadEmail.is_valid.is_(None))
        )
        emails = result.scalars().all()

        validated = 0
        for email_record in emails:
            email_record.is_valid = is_valid_email(email_record.email)
            validated += 1

        return validated

    async def normalize_phones(self, org_id: uuid.UUID) -> int:
        """Normalize all phone numbers for leads in the org."""
        result = await self.db.execute(
            select(LeadPhone)
            .join(Lead)
            .where(Lead.organization_id == org_id, LeadPhone.phone_normalized.is_(None))
        )
        phones = result.scalars().all()

        normalized = 0
        for phone_record in phones:
            if phone_record.phone_raw:
                phone_record.phone_normalized = normalize_phone(phone_record.phone_raw)
                phone_record.phone_type = detect_phone_type(phone_record.phone_raw)
                phone_record.is_valid = phone_record.phone_normalized is not None
                normalized += 1

        return normalized
