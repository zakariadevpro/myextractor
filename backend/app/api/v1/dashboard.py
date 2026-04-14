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
from app.utils.cache import cache_get, cache_set

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

CACHE_TTL = 300  # 5 minutes


@router.get("/overview", response_model=DashboardOverview)
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"dashboard:{current_user.organization_id}:overview"
    cached = await cache_get(cache_key)
    if cached:
        return DashboardOverview(**cached)
    service = DashboardService(db)
    result = await service.get_overview(current_user.organization_id)
    await cache_set(cache_key, result.model_dump(), CACHE_TTL)
    return result


@router.get("/leads-by-sector", response_model=DashboardLeadsBySector)
async def get_leads_by_sector(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"dashboard:{current_user.organization_id}:sector"
    cached = await cache_get(cache_key)
    if cached:
        return DashboardLeadsBySector(**cached)
    service = DashboardService(db)
    data = await service.get_leads_by_sector(current_user.organization_id)
    result = DashboardLeadsBySector(data=data)
    await cache_set(cache_key, result.model_dump(), CACHE_TTL)
    return result


@router.get("/leads-by-zone", response_model=DashboardLeadsByZone)
async def get_leads_by_zone(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"dashboard:{current_user.organization_id}:zone"
    cached = await cache_get(cache_key)
    if cached:
        return DashboardLeadsByZone(**cached)
    service = DashboardService(db)
    data = await service.get_leads_by_zone(current_user.organization_id)
    result = DashboardLeadsByZone(data=data)
    await cache_set(cache_key, result.model_dump(), CACHE_TTL)
    return result


@router.get("/b2c-compliance", response_model=B2CComplianceOverview)
async def get_b2c_compliance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"dashboard:{current_user.organization_id}:b2c"
    cached = await cache_get(cache_key)
    if cached:
        return B2CComplianceOverview(**cached)
    service = DashboardService(db)
    result = await service.get_b2c_compliance_overview(current_user.organization_id)
    await cache_set(cache_key, result.model_dump(), CACHE_TTL)
    return result


@router.get("/lead-intelligence", response_model=LeadIntelligenceOverview)
async def get_lead_intelligence(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"dashboard:{current_user.organization_id}:intelligence"
    cached = await cache_get(cache_key)
    if cached:
        return LeadIntelligenceOverview(**cached)
    service = DashboardService(db)
    result = await service.get_lead_intelligence_overview(current_user.organization_id)
    await cache_set(cache_key, result.model_dump(), CACHE_TTL)
    return result
