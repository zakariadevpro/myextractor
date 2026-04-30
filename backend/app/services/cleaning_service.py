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
        """Recompute is_duplicate (exact same name+city) and is_similar
        (variant via aggressive normalization) flags for the org.

        Returns the total number of leads that ended up flagged
        (duplicates + similars).
        """
        await self.db.execute(
            update(Lead)
            .where(Lead.organization_id == org_id)
            .values(is_duplicate=False, is_similar=False)
        )

        result = await self.db.execute(
            select(Lead.id, Lead.company_name, Lead.city)
            .where(Lead.organization_id == org_id)
            .order_by(Lead.created_at.asc())
        )
        rows = result.all()

        exact_groups: dict[tuple[str, str], list[uuid.UUID]] = {}
        similar_groups: dict[tuple[str, str], list[uuid.UUID]] = {}
        for lead_id, company_name, city in rows:
            name_raw = (company_name or "").strip().lower()
            city_raw = (city or "").strip().lower()
            if name_raw:
                exact_groups.setdefault((name_raw, city_raw), []).append(lead_id)
            similar_key = (
                clean_company_name(company_name or ""),
                clean_text(city or "").upper(),
            )
            if similar_key[0]:
                similar_groups.setdefault(similar_key, []).append(lead_id)

        duplicate_ids: set[uuid.UUID] = {
            lead_id
            for ids in exact_groups.values()
            if len(ids) >= 2
            for lead_id in ids
        }
        similar_ids: set[uuid.UUID] = {
            lead_id
            for ids in similar_groups.values()
            if len(ids) >= 2
            for lead_id in ids
        } - duplicate_ids

        if duplicate_ids:
            await self.db.execute(
                update(Lead)
                .where(Lead.id.in_(duplicate_ids))
                .values(is_duplicate=True)
            )
        if similar_ids:
            await self.db.execute(
                update(Lead)
                .where(Lead.id.in_(similar_ids))
                .values(is_similar=True)
            )

        return len(duplicate_ids) + len(similar_ids)

    async def validate_emails(
        self, org_id: uuid.UUID, *, only_unvalidated: bool = False
    ) -> int:
        """Re-classify is_valid for emails in the org.

        only_unvalidated=True keeps the original behaviour (touch only rows
        with is_valid IS NULL). False (default) re-classifies every row, so
        that placeholder emails inserted before the validator was tightened
        get correctly marked as invalid.
        """
        query = select(LeadEmail).join(Lead).where(Lead.organization_id == org_id)
        if only_unvalidated:
            query = query.where(LeadEmail.is_valid.is_(None))
        result = await self.db.execute(query)
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
