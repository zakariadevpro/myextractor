import unicodedata
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead
from app.models.scoring_profile import ScoringProfile

# Premium sectors that get bonus score
PREMIUM_SECTORS = {
    "assurance",
    "immobilier",
    "banque",
    "finance",
    "energie",
    "telecom",
    "sante",
    "btp",
    "automobile",
    "luxe",
    "conseil",
    "informatique",
}
SOURCE_RELIABILITY_BONUS = {
    "whiteextractor": 16,
    "sirene_api": 12,
    "pages_jaunes": 9,
    "google_maps": 7,
    "meta_lead_ads": 8,
    "web_form": 6,
}

DEFAULT_SCORING_WEIGHTS: dict[str, int] = {
    "valid_email": 22,
    "extra_email": 4,
    "any_email": 8,
    "valid_phone": 14,
    "any_phone": 10,
    "mobile_phone": 5,
    "landline_phone": 3,
    "website": 10,
    "address_3_fields": 10,
    "address_2_fields": 6,
    "siren": 12,
    "naf_code": 6,
    "premium_sector": 8,
    "fallback_source_bonus": 4,
    "duplicate_penalty": 25,
    "no_contact_penalty": 12,
}
DEFAULT_HIGH_THRESHOLD = 80
DEFAULT_MEDIUM_THRESHOLD = 55


@dataclass
class ScoringProfileConfig:
    high_threshold: int
    medium_threshold: int
    weights: dict[str, int]


def _normalize_token(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return normalized.lower().strip()


class ScoringService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def default_profile_config() -> ScoringProfileConfig:
        return ScoringProfileConfig(
            high_threshold=DEFAULT_HIGH_THRESHOLD,
            medium_threshold=DEFAULT_MEDIUM_THRESHOLD,
            weights=dict(DEFAULT_SCORING_WEIGHTS),
        )

    @staticmethod
    def sanitize_weights(weights: dict | None) -> dict[str, int]:
        merged = dict(DEFAULT_SCORING_WEIGHTS)
        if not weights:
            return merged

        for key, value in weights.items():
            if key not in merged:
                continue
            try:
                merged[key] = int(value)
            except (TypeError, ValueError):
                continue
        return merged

    async def get_profile_config(self, org_id: uuid.UUID) -> ScoringProfileConfig:
        result = await self.db.execute(
            select(ScoringProfile).where(ScoringProfile.organization_id == org_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return self.default_profile_config()

        high = max(1, min(100, int(profile.high_threshold)))
        medium = max(0, min(high - 1, int(profile.medium_threshold)))
        weights = self.sanitize_weights(profile.weights)
        return ScoringProfileConfig(high_threshold=high, medium_threshold=medium, weights=weights)

    def calculate_score(self, lead: Lead, weights: dict[str, int] | None = None) -> int:
        """Calculate quality score 0-100 using contactability + data reliability signals."""
        scoring_weights = self.sanitize_weights(weights)
        score = 0

        # Contactability: email quality
        has_valid_email = any(e.is_valid for e in lead.emails if e.is_valid is not None)
        has_any_email = len(lead.emails) > 0
        if has_valid_email:
            score += scoring_weights["valid_email"]
            if len(lead.emails) > 1:
                score += scoring_weights["extra_email"]
        elif has_any_email:
            score += scoring_weights["any_email"]

        # Contactability: phone quality
        has_any_phone = len(lead.phones) > 0
        has_valid_phone = any(p.is_valid is True for p in lead.phones)
        if has_valid_phone:
            score += scoring_weights["valid_phone"]
        elif has_any_phone:
            score += scoring_weights["any_phone"]

        has_mobile = any(p.phone_type == "mobile" for p in lead.phones)
        has_landline = any(p.phone_type == "landline" for p in lead.phones)
        if has_mobile:
            score += scoring_weights["mobile_phone"]
        if has_landline:
            score += scoring_weights["landline_phone"]

        # Company metadata coverage
        if lead.website:
            score += scoring_weights["website"]

        address_fields = sum(
            1 for part in [lead.address, lead.postal_code, lead.city, lead.region] if part
        )
        if address_fields >= 3:
            score += scoring_weights["address_3_fields"]
        elif address_fields == 2:
            score += scoring_weights["address_2_fields"]

        # Official identifiers
        if lead.siren:
            score += scoring_weights["siren"]
        if lead.naf_code:
            score += scoring_weights["naf_code"]

        # Source reliability
        source_key = _normalize_token(lead.source)
        score += SOURCE_RELIABILITY_BONUS.get(source_key, scoring_weights["fallback_source_bonus"])

        # Sector relevance
        sector_key = _normalize_token(lead.sector)
        if any(keyword in sector_key for keyword in PREMIUM_SECTORS):
            score += scoring_weights["premium_sector"]

        # Penalties
        if lead.is_duplicate:
            score -= scoring_weights["duplicate_penalty"]
        if not has_any_email and not has_any_phone:
            score -= scoring_weights["no_contact_penalty"]

        return max(0, min(score, 100))

    async def score_lead(self, lead: Lead) -> int:
        """Score a single lead and update the database."""
        profile = await self.get_profile_config(lead.organization_id)
        score = self.calculate_score(lead, profile.weights)
        lead.quality_score = score
        return score

    async def score_all_unscored(self, org_id: uuid.UUID) -> int:
        """Score all leads with score = 0 in the organization."""
        profile = await self.get_profile_config(org_id)
        result = await self.db.execute(
            select(Lead)
            .options(selectinload(Lead.emails), selectinload(Lead.phones))
            .where(Lead.organization_id == org_id, Lead.quality_score == 0)
        )
        leads = result.scalars().unique().all()

        scored = 0
        for lead in leads:
            lead.quality_score = self.calculate_score(lead, profile.weights)
            scored += 1

        return scored

    async def rescore_all(self, org_id: uuid.UUID) -> int:
        """Recompute score for all leads in the organization using current profile."""
        profile = await self.get_profile_config(org_id)
        result = await self.db.execute(
            select(Lead)
            .options(selectinload(Lead.emails), selectinload(Lead.phones))
            .where(Lead.organization_id == org_id)
        )
        leads = result.scalars().unique().all()

        scored = 0
        for lead in leads:
            lead.quality_score = self.calculate_score(lead, profile.weights)
            scored += 1

        return scored
