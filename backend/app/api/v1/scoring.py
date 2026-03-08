from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.models.user import User
from app.schemas.scoring import (
    ScoringProfileResponse,
    ScoringProfileUpdate,
    ScoringRecomputeResponse,
)
from app.services.audit_log_service import AuditLogService
from app.services.scoring_profile_service import ScoringProfileService
from app.services.scoring_service import ScoringService

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.get("/profile", response_model=ScoringProfileResponse)
async def get_scoring_profile(
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    return await ScoringProfileService(db).get_or_default(current_user.organization_id)


@router.put("/profile", response_model=ScoringProfileResponse)
async def update_scoring_profile(
    payload: ScoringProfileUpdate,
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    profile = await ScoringProfileService(db).upsert(
        current_user.organization_id, current_user, payload
    )
    await AuditLogService(db).log(
        action="scoring.profile_update",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="scoring_profile",
        resource_id=str(profile.id) if profile.id else None,
        details={
            "name": profile.name,
            "high_threshold": profile.high_threshold,
            "medium_threshold": profile.medium_threshold,
            "weights": profile.weights,
        },
    )
    return profile


@router.post("/recompute", response_model=ScoringRecomputeResponse)
async def recompute_scoring(
    current_user: User = Depends(get_current_manager),
    db: AsyncSession = Depends(get_db),
):
    scored = await ScoringService(db).rescore_all(current_user.organization_id)
    await AuditLogService(db).log(
        action="scoring.recompute",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_type="lead",
        details={"rescored": scored},
    )
    return ScoringRecomputeResponse(scored=scored)
