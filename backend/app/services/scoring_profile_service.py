import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scoring_profile import ScoringProfile
from app.models.user import User
from app.schemas.scoring import ScoringProfileResponse, ScoringProfileUpdate
from app.services.scoring_service import ScoringService


class ScoringProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_default(self, org_id: uuid.UUID) -> ScoringProfileResponse:
        result = await self.db.execute(
            select(ScoringProfile).where(ScoringProfile.organization_id == org_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            default = ScoringService.default_profile_config()
            return ScoringProfileResponse(
                id=None,
                name="default",
                high_threshold=default.high_threshold,
                medium_threshold=default.medium_threshold,
                weights=default.weights,
                updated_at=None,
            )

        return ScoringProfileResponse(
            id=profile.id,
            name=profile.name,
            high_threshold=profile.high_threshold,
            medium_threshold=profile.medium_threshold,
            weights=ScoringService.sanitize_weights(profile.weights),
            updated_at=profile.updated_at,
        )

    async def upsert(
        self, org_id: uuid.UUID, actor: User, payload: ScoringProfileUpdate
    ) -> ScoringProfileResponse:
        weights = ScoringService.sanitize_weights(payload.weights)
        result = await self.db.execute(
            select(ScoringProfile).where(ScoringProfile.organization_id == org_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            profile = ScoringProfile(
                organization_id=org_id,
                updated_by=actor.id,
                name=payload.name.strip(),
                high_threshold=payload.high_threshold,
                medium_threshold=payload.medium_threshold,
                weights=weights,
            )
            self.db.add(profile)
        else:
            profile.name = payload.name.strip()
            profile.updated_by = actor.id
            profile.high_threshold = payload.high_threshold
            profile.medium_threshold = payload.medium_threshold
            profile.weights = weights

        await self.db.flush()
        return ScoringProfileResponse(
            id=profile.id,
            name=profile.name,
            high_threshold=profile.high_threshold,
            medium_threshold=profile.medium_threshold,
            weights=ScoringService.sanitize_weights(profile.weights),
            updated_at=profile.updated_at,
        )
