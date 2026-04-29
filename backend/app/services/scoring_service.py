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
    # Trio essentiel: adresse + telephone + email = "warm lead".
    # Ce sont les donnees principales qu'on cherche, donc gros bonus
    # pour pousser ces leads dans le tier "warm" (ex-Excellent).
    "core_contact_bonus": 20,
    "duplicate_penalty": 25,
    "no_contact_penalty": 12,
}
DEFAULT_HIGH_THRESHOLD = 70
DEFAULT_MEDIUM_THRESHOLD = 40


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
        return self.calculate_score_breakdown(lead, weights)["score"]

    def calculate_score_breakdown(
        self, lead: Lead, weights: dict[str, int] | None = None
    ) -> dict:
        """Compute the score AND return the line-by-line breakdown.

        Why: two leads can show the same primary email/phone in the table yet have
        very different scores because the score depends on hidden fields (SIREN,
        NAF, source, is_duplicate, mobile vs landline, email validity, etc.).
        Returning the breakdown lets the UI explain the score to the user.
        """
        scoring_weights = self.sanitize_weights(weights)
        items: list[dict] = []
        raw_total = 0

        def add(label: str, key: str, applied: bool, detail: str | None = None) -> None:
            nonlocal raw_total
            points = scoring_weights.get(key, 0)
            if applied:
                raw_total += points
            items.append(
                {
                    "label": label,
                    "key": key,
                    "points": points,
                    "applied": applied,
                    "detail": detail,
                }
            )

        def add_signed(
            label: str, points: int, applied: bool, detail: str | None = None,
            key: str | None = None,
        ) -> None:
            nonlocal raw_total
            if applied:
                raw_total += points
            items.append(
                {
                    "label": label,
                    "key": key or label,
                    "points": points,
                    "applied": applied,
                    "detail": detail,
                }
            )

        # Email
        emails = list(lead.emails)
        has_any_email = len(emails) > 0
        has_valid_email = any(e.is_valid for e in emails if e.is_valid is not None)
        primary_email_value = emails[0].email if emails else None
        if has_valid_email:
            add(
                "Email valide",
                "valid_email",
                True,
                detail=primary_email_value,
            )
        elif has_any_email:
            add(
                "Email present (non valide)",
                "any_email",
                True,
                detail=primary_email_value,
            )
        else:
            add("Aucun email", "valid_email", False)

        if has_valid_email and len(emails) > 1:
            add(
                "Email supplementaire",
                "extra_email",
                True,
                detail=f"{len(emails)} emails au total",
            )

        # Phone
        phones = list(lead.phones)
        has_any_phone = len(phones) > 0
        has_valid_phone = any(p.is_valid is True for p in phones)
        primary_phone_value = (
            phones[0].phone_normalized or phones[0].phone_raw if phones else None
        )
        if has_valid_phone:
            add("Telephone valide", "valid_phone", True, detail=primary_phone_value)
        elif has_any_phone:
            add(
                "Telephone present (non valide)",
                "any_phone",
                True,
                detail=primary_phone_value,
            )
        else:
            add("Aucun telephone", "valid_phone", False)

        has_mobile = any(p.phone_type == "mobile" for p in phones)
        has_landline = any(p.phone_type == "landline" for p in phones)
        if has_mobile:
            add("Telephone mobile", "mobile_phone", True)
        if has_landline:
            add("Telephone fixe", "landline_phone", True)

        # Website
        if lead.website:
            add("Site web", "website", True, detail=lead.website)
        else:
            add("Site web absent", "website", False)

        # Address completeness
        address_fields = sum(
            1 for part in [lead.address, lead.postal_code, lead.city, lead.region] if part
        )
        if address_fields >= 3:
            add(
                "Adresse complete (>=3 champs)",
                "address_3_fields",
                True,
                detail=f"{address_fields}/4 champs renseignes",
            )
        elif address_fields == 2:
            add("Adresse partielle (2 champs)", "address_2_fields", True)
        else:
            add(
                "Adresse incomplete",
                "address_3_fields",
                False,
                detail=f"{address_fields}/4 champs renseignes",
            )

        # Official identifiers
        add(
            "SIREN",
            "siren",
            bool(lead.siren),
            detail=lead.siren if lead.siren else None,
        )
        add(
            "Code NAF",
            "naf_code",
            bool(lead.naf_code),
            detail=lead.naf_code if lead.naf_code else None,
        )

        # Source reliability (always applies, fallback if unknown)
        source_key = _normalize_token(lead.source)
        source_points = SOURCE_RELIABILITY_BONUS.get(source_key)
        if source_points is not None:
            add_signed(
                f"Source: {lead.source}",
                source_points,
                True,
                detail="Bonus fiabilite source",
                key="source_bonus",
            )
        else:
            add_signed(
                f"Source: {lead.source or 'inconnue'}",
                scoring_weights["fallback_source_bonus"],
                True,
                detail="Bonus fallback (source non listee)",
                key="fallback_source_bonus",
            )

        # Sector
        sector_key = _normalize_token(lead.sector)
        is_premium_sector = bool(
            sector_key and any(keyword in sector_key for keyword in PREMIUM_SECTORS)
        )
        add(
            "Secteur premium",
            "premium_sector",
            is_premium_sector,
            detail=lead.sector if lead.sector else None,
        )

        # Trio essentiel: adresse + telephone + email -> "warm lead".
        # Address must be substantively complete (>=3 fields), phone and email
        # just need to be present. This is the prospect data we actually need.
        is_warm = address_fields >= 3 and has_any_phone and has_any_email
        add(
            "Trio essentiel (adresse + tel + email) -> Warm",
            "core_contact_bonus",
            is_warm,
            detail=(
                "Lead qualifie warm" if is_warm
                else "Manque au moins une donnee principale"
            ),
        )

        # Penalties (negative)
        if lead.is_duplicate:
            add_signed(
                "Doublon (penalite)",
                -scoring_weights["duplicate_penalty"],
                True,
                detail="Lead marque comme doublon",
                key="duplicate_penalty",
            )
        if not has_any_email and not has_any_phone:
            add_signed(
                "Aucun contact (penalite)",
                -scoring_weights["no_contact_penalty"],
                True,
                detail="Ni email ni telephone",
                key="no_contact_penalty",
            )

        clamped = max(0, min(raw_total, 100))
        return {
            "score": clamped,
            "raw_total": raw_total,
            "items": items,
        }

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
