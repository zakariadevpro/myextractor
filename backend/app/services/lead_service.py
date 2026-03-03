import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead


class LeadService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, lead_id: uuid.UUID, org_id: uuid.UUID) -> Lead | None:
        result = await self.db.execute(
            select(Lead)
            .options(selectinload(Lead.emails), selectinload(Lead.phones))
            .where(Lead.id == lead_id, Lead.organization_id == org_id)
        )
        return result.scalar_one_or_none()

    async def check_duplicate(
        self,
        company_name: str,
        city: str | None,
        org_id: uuid.UUID,
    ) -> Lead | None:
        """Check if a lead with same name and city already exists."""
        query = select(Lead).where(
            Lead.organization_id == org_id,
            Lead.company_name.ilike(company_name.strip()),
        )
        if city:
            query = query.where(Lead.city.ilike(city.strip()))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
