from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    B2CComplianceOverview,
    DashboardLeadsBySector,
    DashboardLeadsByZone,
    DashboardOverview,
    LeadIntelligenceOverview,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    return await service.get_overview(current_user.organization_id)


@router.get("/leads-by-sector", response_model=DashboardLeadsBySector)
async def get_leads_by_sector(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    data = await service.get_leads_by_sector(current_user.organization_id)
    return DashboardLeadsBySector(data=data)


@router.get("/leads-by-zone", response_model=DashboardLeadsByZone)
async def get_leads_by_zone(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    data = await service.get_leads_by_zone(current_user.organization_id)
    return DashboardLeadsByZone(data=data)


@router.get("/b2c-compliance", response_model=B2CComplianceOverview)
async def get_b2c_compliance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    return await service.get_b2c_compliance_overview(current_user.organization_id)


@router.get("/lead-intelligence", response_model=LeadIntelligenceOverview)
async def get_lead_intelligence(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    return await service.get_lead_intelligence_overview(current_user.organization_id)
