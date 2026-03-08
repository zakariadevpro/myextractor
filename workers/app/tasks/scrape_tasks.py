import asyncio
import json
import logging
import re
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.scrapers.base import ScrapedLead
from app.scrapers.google_maps import GoogleMapsScraper
from app.scrapers.pages_jaunes import PagesJaunesScraper
from app.scrapers.sirene_api import SireneApiScraper

logger = logging.getLogger(__name__)

# Sync engine for Celery tasks (Celery doesn't support async natively)
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)

COMPANY_LEGAL_SUFFIXES = {
    "sas",
    "sarl",
    "sa",
    "eurl",
    "sasu",
    "sci",
    "snc",
    "scp",
    "selarl",
    "holding",
}
PERSONAL_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "yahoo.com",
    "yahoo.fr",
    "icloud.com",
    "proton.me",
    "protonmail.com",
    "orange.fr",
    "wanadoo.fr",
    "free.fr",
    "laposte.net",
    "gmx.fr",
}
B2B_HINT_TOKENS = {
    "entreprise",
    "societe",
    "cabinet",
    "agence",
    "atelier",
    "garage",
    "restaurant",
    "hotel",
    "immobilier",
    "consulting",
    "services",
    "transport",
    "batiment",
    "travaux",
    "plomberie",
    "electricite",
    "boulangerie",
    "boucherie",
    "pharmacie",
    "clinique",
    "veterinaire",
    "commerce",
    "boutique",
}
CIVILITY_TOKENS = {"mr", "mme", "mlle", "monsieur", "madame", "mademoiselle"}
COMMON_FIRST_NAMES = {
    "jean",
    "marie",
    "pierre",
    "paul",
    "jacques",
    "louis",
    "nicolas",
    "antoine",
    "julien",
    "sophie",
    "camille",
    "lea",
    "emma",
    "lucas",
    "hugo",
    "thomas",
    "alexandre",
    "mehdi",
    "karim",
    "kevin",
    "sarah",
    "laura",
    "manon",
    "chloe",
    "nathalie",
    "isabelle",
}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
DEFAULT_SCORING_WEIGHTS = {
    "valid_email": 22,
    "extra_email": 4,
    "any_email": 8,
    "valid_phone": 14,
    "any_phone": 10,
    "mobile_phone": 5,
    "landline_phone": 3,
    "website": 10,
    "pro_email_bonus": 10,
    "email_website_domain_match_bonus": 6,
    "multi_phone_bonus": 4,
    "full_contact_profile_bonus": 6,
    "address_3_fields": 10,
    "address_2_fields": 6,
    "siren": 12,
    "naf_code": 6,
    "fallback_source_bonus": 4,
    "duplicate_penalty": 25,
}


def _get_or_create_event_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def _run_async(coro):
    loop = _get_or_create_event_loop()
    return loop.run_until_complete(coro)


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"\s+", " ", normalized).strip().lower()


def _normalize_company_for_key(company_name: str) -> str:
    raw = _normalize_text(company_name)
    tokens = [tok for tok in re.split(r"[^a-z0-9]+", raw) if tok]
    filtered = [tok for tok in tokens if tok not in COMPANY_LEGAL_SUFFIXES]
    return " ".join(filtered)


def _normalize_city_for_key(city: str | None) -> str:
    return _normalize_text(city)


def _canonical_website(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    candidate = raw_url.strip()
    if not candidate:
        return None
    if not re.match(r"^https?://", candidate, flags=re.IGNORECASE):
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if not parsed.netloc:
        return None
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


def _clean_email_list(emails: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for email in emails:
        value = (email or "").strip().lower()
        if not value or value in seen:
            continue
        if not EMAIL_RE.match(value):
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned[:5]


def _clean_phone_list(phones: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for phone in phones:
        value = (phone or "").strip()
        if not value:
            continue
        key = re.sub(r"[^\d+]", "", value)
        if len(key) < 10 or key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned[:5]


def _email_domain(email: str) -> str:
    value = (email or "").strip().lower()
    if "@" not in value:
        return ""
    return value.rsplit("@", 1)[1]


def _has_professional_email(lead: ScrapedLead) -> bool:
    for email in lead.emails or []:
        domain = _email_domain(email)
        if domain and domain not in PERSONAL_EMAIL_DOMAINS:
            return True
    return False


def _has_personal_email(lead: ScrapedLead) -> bool:
    for email in lead.emails or []:
        domain = _email_domain(email)
        if domain and domain in PERSONAL_EMAIL_DOMAINS:
            return True
    return False


def _website_domain(website: str | None) -> str:
    canonical = _canonical_website(website)
    if not canonical:
        return ""
    netloc = urlparse(canonical).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _has_email_website_domain_match(lead: ScrapedLead) -> bool:
    site_domain = _website_domain(lead.website)
    if not site_domain:
        return False
    for email in lead.emails or []:
        email_domain = _email_domain(email)
        if not email_domain:
            continue
        if email_domain == site_domain:
            return True
        if site_domain.endswith(f".{email_domain}") or email_domain.endswith(
            f".{site_domain}"
        ):
            return True
    return False


def _professional_email_count(lead: ScrapedLead) -> int:
    return sum(
        1
        for email in (lead.emails or [])
        if _email_domain(email) not in PERSONAL_EMAIL_DOMAINS
    )


def _normalize_phone_for_storage(phone: str) -> str | None:
    normalized = re.sub(r"[^\d+]", "", (phone or "").strip())
    if len(normalized) < 10:
        return None
    if normalized.startswith("00"):
        normalized = f"+{normalized[2:]}"
    if normalized.startswith("0") and len(normalized) == 10:
        normalized = f"+33{normalized[1:]}"
    return normalized


def _detect_phone_type(phone: str) -> str:
    normalized = _normalize_phone_for_storage(phone)
    if not normalized:
        return "unknown"
    if normalized.startswith("+336") or normalized.startswith("+337"):
        return "mobile"
    return "landline"


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clamp_score(value: int) -> int:
    return max(0, min(value, 100))


def _load_scoring_weights(db, organization_id: str) -> dict[str, int]:
    weights = dict(DEFAULT_SCORING_WEIGHTS)
    row = (
        db.execute(
            text(
                """
            SELECT weights
            FROM scoring_profiles
            WHERE organization_id = :org_id
            LIMIT 1
            """
            ),
            {"org_id": organization_id},
        )
        .mappings()
        .first()
    )
    if not row:
        return weights

    raw_weights = row.get("weights") or {}
    if isinstance(raw_weights, str):
        try:
            raw_weights = json.loads(raw_weights)
        except json.JSONDecodeError:
            raw_weights = {}

    if isinstance(raw_weights, dict):
        for key in list(weights.keys()):
            if key in raw_weights:
                weights[key] = _safe_int(raw_weights[key], weights[key])
    return weights


def _compute_initial_quality(
    lead: ScrapedLead,
    source: str,
    is_duplicate: bool,
    weights: dict[str, int] | None = None,
) -> int:
    scoring_weights = weights or DEFAULT_SCORING_WEIGHTS
    score = 0
    if lead.emails:
        score += scoring_weights.get("valid_email", 22)
        if len(lead.emails) > 1:
            score += scoring_weights.get("extra_email", 4)
        if _has_professional_email(lead):
            score += scoring_weights.get(
                "pro_email_bonus", settings.contact_pro_email_bonus
            )
        if _has_email_website_domain_match(lead):
            score += scoring_weights.get(
                "email_website_domain_match_bonus",
                settings.contact_email_website_domain_match_bonus,
            )
    if lead.phones:
        score += scoring_weights.get("valid_phone", 14)
        if any(_detect_phone_type(phone) == "mobile" for phone in lead.phones):
            score += scoring_weights.get("mobile_phone", 5)
        if len(lead.phones) > 1:
            score += scoring_weights.get(
                "multi_phone_bonus", settings.contact_multi_phone_bonus
            )
    if lead.website:
        score += scoring_weights.get("website", 10)
    if lead.website and lead.phones and _has_professional_email(lead):
        score += scoring_weights.get(
            "full_contact_profile_bonus", settings.contact_full_profile_bonus
        )
    if lead.address and lead.postal_code and lead.city:
        score += scoring_weights.get("address_3_fields", 10)
    if lead.siren:
        score += scoring_weights.get("siren", 12)
    if lead.naf_code:
        score += scoring_weights.get("naf_code", 6)
    source_bonus = {
        "whiteextractor": 16,
        "sirene_api": 12,
        "pages_jaunes": 9,
        "google_maps": 7,
    }
    score += source_bonus.get(source, scoring_weights.get("fallback_source_bonus", 4))
    if is_duplicate:
        score -= scoring_weights.get("duplicate_penalty", 25)
    return _clamp_score(score)


def _sanitize_scraped_lead(lead: ScrapedLead) -> ScrapedLead | None:
    lead.company_name = re.sub(r"\s+", " ", (lead.company_name or "")).strip()
    if len(lead.company_name) < 2:
        return None
    lead.city = re.sub(r"\s+", " ", (lead.city or "")).strip()
    lead.address = re.sub(r"\s+", " ", (lead.address or "")).strip()
    lead.sector = re.sub(r"\s+", " ", (lead.sector or "")).strip()
    lead.website = _canonical_website(lead.website) or ""
    lead.source_url = (
        _canonical_website(lead.source_url) or (lead.source_url or "").strip()
    )
    lead.siren = re.sub(r"\D", "", (lead.siren or ""))[:9]
    lead.postal_code = re.sub(r"\D", "", (lead.postal_code or ""))[:5]
    lead.emails = _clean_email_list(lead.emails or [])
    lead.phones = _clean_phone_list(lead.phones or [])
    return lead


def _is_likely_individual_name(company_name: str) -> bool:
    normalized = _normalize_text(company_name)
    if not normalized:
        return False
    tokens = [tok for tok in re.split(r"[^a-z0-9]+", normalized) if tok]
    if not tokens:
        return False
    if any(tok in CIVILITY_TOKENS for tok in tokens):
        return True
    if len(tokens) in {2, 3} and all(tok.isalpha() for tok in tokens):
        if tokens[0] in COMMON_FIRST_NAMES:
            return True
    return False


def _has_business_name_hints(company_name: str) -> bool:
    normalized = _normalize_text(company_name)
    if not normalized:
        return False
    tokens = [tok for tok in re.split(r"[^a-z0-9]+", normalized) if tok]
    token_set = set(tokens)
    if token_set.intersection(COMPANY_LEGAL_SUFFIXES):
        return True
    if token_set.intersection(B2B_HINT_TOKENS):
        return True
    return False


def _has_strong_b2b_identity(lead: ScrapedLead) -> bool:
    return bool(
        lead.siren or lead.naf_code or _has_business_name_hints(lead.company_name)
    )


def _is_b2b_candidate(lead: ScrapedLead) -> bool:
    # Strong business signals first.
    if lead.siren or lead.naf_code:
        return True
    if _has_business_name_hints(lead.company_name):
        return True
    if _has_professional_email(lead):
        return True
    if lead.website:
        return True
    if lead.sector and len(_normalize_text(lead.sector)) >= 3:
        return True

    # Reject records that look like person names and have no business signal.
    if _is_likely_individual_name(lead.company_name):
        return False

    # Strict B2B mode: unknown entities are rejected by default.
    return False


def _query_has_person_intent(keywords: list[str] | None) -> bool:
    if not keywords:
        return False
    tokens: list[str] = []
    for value in keywords:
        normalized = _normalize_text(value)
        if not normalized:
            continue
        tokens.extend(tok for tok in re.split(r"[^a-z0-9]+", normalized) if tok)
    if not tokens:
        return False

    token_set = set(tokens)
    if token_set.intersection(CIVILITY_TOKENS):
        return True
    if token_set.intersection(COMMON_FIRST_NAMES):
        return True
    if token_set.intersection(B2B_HINT_TOKENS) or token_set.intersection(
        COMPANY_LEGAL_SUFFIXES
    ):
        return False

    alpha_tokens = [tok for tok in tokens if tok.isalpha()]
    return 1 <= len(alpha_tokens) <= 3


def _normalize_target_kind(target_kind: str | None) -> str:
    value = str(target_kind or "both").strip().lower()
    if value not in {"b2b", "b2c", "both"}:
        return "both"
    return value


def _classify_lead_kind(lead: ScrapedLead) -> str:
    b2b_signal = _is_b2b_candidate(lead)
    b2c_signal = _is_likely_individual_name(lead.company_name) or (
        _has_personal_email(lead) and not _has_professional_email(lead)
    )
    if b2b_signal and not b2c_signal:
        return "b2b"
    if b2c_signal and not b2b_signal:
        return "b2c"
    if b2b_signal and b2c_signal:
        # Mixed signal: keep as B2B if there is an official/company indicator.
        if lead.siren or lead.naf_code or _has_business_name_hints(lead.company_name):
            return "b2b"
        return "b2c"
    return "unknown"


def _filter_by_target_kind(
    leads: list[ScrapedLead],
    target_kind: str,
    query_keywords: list[str] | None = None,
) -> tuple[list[tuple[ScrapedLead, str]], dict[str, int]]:
    selected: list[tuple[ScrapedLead, str]] = []
    counts = {
        "raw": len(leads),
        "class_b2b": 0,
        "class_b2c": 0,
        "class_unknown": 0,
        "filtered_out": 0,
    }
    normalized_target = _normalize_target_kind(target_kind)
    strict_unknown = bool(settings.b2b_strict_mode)
    person_query = normalized_target == "b2c" and _query_has_person_intent(
        query_keywords
    )

    for lead in leads:
        classified = _classify_lead_kind(lead)
        if classified == "b2b":
            counts["class_b2b"] += 1
        elif classified == "b2c":
            counts["class_b2c"] += 1
        else:
            counts["class_unknown"] += 1

        keep = False
        stored_kind = classified if classified in {"b2b", "b2c"} else "b2b"

        if normalized_target == "both":
            if classified in {"b2b", "b2c"}:
                keep = True
            elif not strict_unknown:
                keep = True
                stored_kind = "b2b"
        elif normalized_target == "b2b":
            if classified == "b2b":
                keep = True
            elif classified == "unknown" and not strict_unknown:
                keep = True
                stored_kind = "b2b"
        elif normalized_target == "b2c":
            if classified == "b2c":
                keep = True
            elif classified == "unknown":
                keep = True
                stored_kind = "b2c"
            elif (
                person_query
                and classified == "b2b"
                and not _has_strong_b2b_identity(lead)
            ):
                keep = True
                stored_kind = "b2c"

        if keep:
            selected.append((lead, stored_kind))
        else:
            counts["filtered_out"] += 1

    return selected, counts


def _lead_key(lead: ScrapedLead) -> str | None:
    if lead.siren:
        return f"siren:{lead.siren}"
    company_key = _normalize_company_for_key(lead.company_name)
    if not company_key:
        return None
    city_key = _normalize_city_for_key(lead.city)
    return f"name:{company_key}|city:{city_key}"


def _merge_leads(base: ScrapedLead, incoming: ScrapedLead) -> ScrapedLead:
    # Keep strongest identity fields from official/public sources when available.
    if not base.siren and incoming.siren:
        base.siren = incoming.siren
    if not base.naf_code and incoming.naf_code:
        base.naf_code = incoming.naf_code
    if not base.sector and incoming.sector:
        base.sector = incoming.sector
    if not base.website and incoming.website:
        base.website = incoming.website
    if not base.source_url and incoming.source_url:
        base.source_url = incoming.source_url
    if not base.address and incoming.address:
        base.address = incoming.address
    if not base.postal_code and incoming.postal_code:
        base.postal_code = incoming.postal_code
    if not base.city and incoming.city:
        base.city = incoming.city
    if not base.department and incoming.department:
        base.department = incoming.department
    if not base.region and incoming.region:
        base.region = incoming.region

    base.emails = _clean_email_list((base.emails or []) + (incoming.emails or []))
    base.phones = _clean_phone_list((base.phones or []) + (incoming.phones or []))
    return base


def _dedupe_and_merge_scraped_leads(
    leads: list[ScrapedLead], max_results: int
) -> list[ScrapedLead]:
    merged: dict[str, ScrapedLead] = {}
    ordered_keys: list[str] = []
    for lead in leads:
        sanitized = _sanitize_scraped_lead(lead)
        if not sanitized:
            continue
        key = _lead_key(sanitized)
        if not key:
            continue
        if key in merged:
            merged[key] = _merge_leads(merged[key], sanitized)
        else:
            merged[key] = sanitized
            ordered_keys.append(key)
        if len(ordered_keys) >= max_results:
            # Continue merging duplicates of already selected leads, but ignore new keys.
            continue
    return [merged[key] for key in ordered_keys[:max_results]]


def _get_scraper(source: str):
    """Factory: return the right scraper instance for the given source."""
    scrapers = {
        "google_maps": GoogleMapsScraper,
        "pages_jaunes": PagesJaunesScraper,
        "sirene_api": SireneApiScraper,
    }
    cls = scrapers.get(source)
    if cls is None:
        raise ValueError(f"Unknown source: {source}")
    return cls()


async def _run_single_source_search(
    *,
    source: str,
    keywords: list[str],
    city: str | None,
    radius_km: int | None,
    max_results: int,
) -> list[ScrapedLead]:
    scraper = _get_scraper(source)
    try:
        return await scraper.search(
            keywords=keywords,
            city=city,
            radius_km=radius_km,
            max_results=max_results,
        )
    finally:
        await scraper.close()


async def _run_whiteextractor_search(
    *,
    keywords: list[str],
    city: str | None,
    radius_km: int | None,
    max_results: int,
    target_kind: str = "both",
) -> list[ScrapedLead]:
    """
    WhiteExtractor mode:
    1) Official data enrichment (Sirene)
    2) Contact/annuaire coverage (Pages Jaunes)
    3) Fresh local business signals (Google Maps)
    """
    all_leads: list[ScrapedLead] = []
    normalized_target = _normalize_target_kind(target_kind)
    if normalized_target == "b2c":
        source_order = ["pages_jaunes", "google_maps"]
    else:
        source_order = ["sirene_api", "pages_jaunes", "google_maps"]
    for source_name in source_order:
        try:
            leads = await _run_single_source_search(
                source=source_name,
                keywords=keywords,
                city=city,
                radius_km=radius_km,
                max_results=max_results,
            )
            logger.info(
                f"WhiteExtractor source={source_name} returned {len(leads)} leads"
            )
            all_leads.extend(leads)
        except Exception as exc:
            logger.warning(f"WhiteExtractor source={source_name} failed: {exc}")
            continue
    merged = _dedupe_and_merge_scraped_leads(all_leads, max_results=max_results)
    logger.info(
        f"WhiteExtractor merged {len(all_leads)} raw leads into {len(merged)} unique leads"
    )
    return merged


def _match_workflow_conditions(lead_row: dict, conditions: dict) -> bool:
    if not conditions:
        return True

    min_score = conditions.get("min_score")
    if min_score is not None and _safe_int(
        lead_row.get("quality_score"), 0
    ) < _safe_int(min_score, 0):
        return False

    max_score = conditions.get("max_score")
    if max_score is not None and _safe_int(
        lead_row.get("quality_score"), 0
    ) > _safe_int(max_score, 100):
        return False

    lead_kind = conditions.get("lead_kind")
    if (
        lead_kind
        and str(lead_row.get("lead_kind", "")).lower() != str(lead_kind).lower()
    ):
        return False

    source_in = conditions.get("source_in")
    if isinstance(source_in, list) and source_in:
        allowed = {str(item).strip().lower() for item in source_in}
        if str(lead_row.get("source", "")).lower() not in allowed:
            return False

    city_contains = str(conditions.get("city_contains") or "").strip().lower()
    if city_contains:
        city_value = str(lead_row.get("city") or "").lower()
        if city_contains not in city_value:
            return False

    has_email = conditions.get("has_email")
    if has_email is not None:
        email_count = _safe_int(lead_row.get("email_count"), 0)
        if bool(email_count > 0) != _to_bool(has_email):
            return False

    has_phone = conditions.get("has_phone")
    if has_phone is not None:
        phone_count = _safe_int(lead_row.get("phone_count"), 0)
        if bool(phone_count > 0) != _to_bool(has_phone):
            return False

    is_duplicate = conditions.get("is_duplicate")
    if is_duplicate is not None:
        if bool(lead_row.get("is_duplicate")) != _to_bool(is_duplicate):
            return False

    return True


def _apply_workflow_actions(lead_row: dict, actions: dict) -> dict:
    updates = {}
    if "score_delta" in actions:
        current = _safe_int(lead_row.get("quality_score"), 0)
        delta = _safe_int(actions.get("score_delta"), 0)
        updates["quality_score"] = _clamp_score(current + delta)

    if "set_lead_kind" in actions:
        lead_kind = str(actions.get("set_lead_kind") or "").strip().lower()
        if lead_kind in {"b2b", "b2c"}:
            updates["lead_kind"] = lead_kind

    if "mark_duplicate" in actions:
        updates["is_duplicate"] = _to_bool(actions.get("mark_duplicate"))

    if "set_source" in actions:
        source_value = str(actions.get("set_source") or "").strip()
        if source_value:
            updates["source"] = source_value

    return updates


def _run_post_extraction_workflows(db, organization_id: str, job_id: str) -> dict:
    workflow_rows = (
        db.execute(
            text(
                """
            SELECT id, conditions, actions
            FROM automation_workflows
            WHERE organization_id = :org_id
              AND is_active = true
              AND trigger_event = 'post_extraction'
            ORDER BY created_at ASC
            """
            ),
            {"org_id": organization_id},
        )
        .mappings()
        .all()
    )
    if not workflow_rows:
        return {"workflows": 0, "matched": 0, "updated": 0}

    lead_rows = (
        db.execute(
            text(
                """
            SELECT
              l.id,
              l.quality_score,
              l.lead_kind,
              l.source,
              l.city,
              l.is_duplicate,
              (
                SELECT count(1)
                FROM lead_emails e
                WHERE e.lead_id = l.id
              ) AS email_count,
              (
                SELECT count(1)
                FROM lead_phones p
                WHERE p.lead_id = l.id
              ) AS phone_count
            FROM leads l
            WHERE l.organization_id = :org_id
              AND l.extraction_job_id = CAST(:job_id AS uuid)
            """
            ),
            {"org_id": organization_id, "job_id": job_id},
        )
        .mappings()
        .all()
    )

    total_matched = 0
    total_updated = 0
    for workflow in workflow_rows:
        raw_conditions = workflow.get("conditions") or {}
        raw_actions = workflow.get("actions") or {}
        conditions = raw_conditions if isinstance(raw_conditions, dict) else {}
        actions = raw_actions if isinstance(raw_actions, dict) else {}

        for lead in lead_rows:
            lead_state = dict(lead)
            if not _match_workflow_conditions(lead_state, conditions):
                continue

            total_matched += 1
            updates = _apply_workflow_actions(lead_state, actions)
            if not updates:
                continue

            changed = False
            for field, value in updates.items():
                if lead_state.get(field) != value:
                    changed = True
                    break
            if not changed:
                continue

            db.execute(
                text(
                    """
                    UPDATE leads
                    SET quality_score = COALESCE(:quality_score, quality_score),
                        lead_kind = COALESCE(:lead_kind, lead_kind),
                        source = COALESCE(:source, source),
                        is_duplicate = COALESCE(:is_duplicate, is_duplicate),
                        updated_at = :updated_at
                    WHERE id = CAST(:lead_id AS uuid)
                    """
                ),
                {
                    "lead_id": lead_state["id"],
                    "quality_score": updates.get("quality_score"),
                    "lead_kind": updates.get("lead_kind"),
                    "source": updates.get("source"),
                    "is_duplicate": updates.get("is_duplicate"),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            total_updated += 1

    db.execute(
        text(
            """
            UPDATE automation_workflows
            SET last_run_at = :now, updated_at = :now
            WHERE organization_id = :org_id
              AND is_active = true
              AND trigger_event = 'post_extraction'
            """
        ),
        {"org_id": organization_id, "now": datetime.now(timezone.utc)},
    )

    return {
        "workflows": len(workflow_rows),
        "matched": total_matched,
        "updated": total_updated,
    }


@celery_app.task(
    name="workers.tasks.scrape_tasks.execute_scraping",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def execute_scraping(self, job_id: str, target_kind: str = "both"):
    """Execute a scraping job."""
    db = SessionLocal()
    job_started_monotonic = time.monotonic()
    try:
        # Get job details
        result = db.execute(
            text("SELECT * FROM extraction_jobs WHERE id = :id"),
            {"id": job_id},
        )
        job = result.mappings().first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        if job["status"] == "cancelled":
            logger.info(f"Job {job_id} was cancelled")
            return

        # Update status to running
        db.execute(
            text(
                "UPDATE extraction_jobs SET status = 'running', started_at = :now WHERE id = :id"
            ),
            {"id": job_id, "now": datetime.now(timezone.utc)},
        )
        db.commit()

        # Run the scraper
        keywords = job["keywords"] or []
        city = job["city"]
        radius_km = job["radius_km"]
        max_leads = job["max_leads"] or 100
        source = job["source"] or "google_maps"
        target_kind = _normalize_target_kind(target_kind)
        scoring_weights = _load_scoring_weights(db, str(job["organization_id"]))

        if source == "whiteextractor":
            scraped_leads = _run_async(
                _run_whiteextractor_search(
                    keywords=keywords,
                    city=city,
                    radius_km=radius_km,
                    max_results=max_leads,
                    target_kind=target_kind,
                )
            )
        else:
            scraped_leads = _run_async(
                _run_single_source_search(
                    source=source,
                    keywords=keywords,
                    city=city,
                    radius_km=radius_km,
                    max_results=max_leads,
                )
            )
            scraped_leads = _dedupe_and_merge_scraped_leads(
                scraped_leads,
                max_results=max_leads,
            )

        raw_scraped_count = len(scraped_leads)
        selected_leads, filter_counts = _filter_by_target_kind(
            scraped_leads,
            target_kind,
            query_keywords=keywords,
        )
        if len(selected_leads) > max_leads:
            selected_leads = selected_leads[:max_leads]
        leads_with_phone = sum(1 for lead, _ in selected_leads if lead.phones)
        leads_with_pro_email = sum(
            1 for lead, _ in selected_leads if _professional_email_count(lead) > 0
        )
        logger.info(
            "Job %s target_kind=%s filtering: raw=%s kept=%s filtered_out=%s (b2b=%s b2c=%s unknown=%s)",
            job_id,
            target_kind,
            filter_counts["raw"],
            len(selected_leads),
            filter_counts["filtered_out"],
            filter_counts["class_b2b"],
            filter_counts["class_b2c"],
            filter_counts["class_unknown"],
        )

        # Store leads in database
        leads_new = 0
        leads_duplicate = 0

        for scraped, detected_lead_kind in selected_leads:
            # Check for duplicates (same name + city in same org)
            dup_check = db.execute(
                text("""
                    SELECT id FROM leads
                    WHERE organization_id = :org_id
                    AND LOWER(company_name) = LOWER(:name)
                    AND LOWER(COALESCE(city, '')) = LOWER(COALESCE(:city, ''))
                """),
                {
                    "org_id": str(job["organization_id"]),
                    "name": scraped.company_name,
                    "city": scraped.city,
                },
            )
            existing = dup_check.first()

            lead_id = str(uuid.uuid4())
            is_duplicate = existing is not None

            if is_duplicate:
                leads_duplicate += 1
            else:
                leads_new += 1
            quality_score = _compute_initial_quality(
                scraped,
                source=source,
                is_duplicate=is_duplicate,
                weights=scoring_weights,
            )

            # Insert lead
            db.execute(
                text("""
                    INSERT INTO leads (
                        id, organization_id, extraction_job_id, company_name,
                        siren, naf_code, sector, website, address, postal_code,
                        city, department, region, country, source, source_url, lead_kind, is_duplicate, quality_score
                    ) VALUES (
                        :id, :org_id, :job_id, :name,
                        :siren, :naf, :sector, :website, :address, :postal,
                        :city, :dept, :region, 'FR', :source, :source_url, :lead_kind, :is_dup, :quality_score
                    )
                """),
                {
                    "id": lead_id,
                    "org_id": str(job["organization_id"]),
                    "job_id": job_id,
                    "name": scraped.company_name,
                    "siren": scraped.siren or None,
                    "naf": scraped.naf_code or None,
                    "sector": scraped.sector or None,
                    "website": scraped.website or None,
                    "address": scraped.address or None,
                    "postal": scraped.postal_code or None,
                    "city": scraped.city or None,
                    "dept": scraped.department or None,
                    "region": scraped.region or None,
                    "source": source,
                    "source_url": scraped.source_url or None,
                    "lead_kind": detected_lead_kind,
                    "is_dup": is_duplicate,
                    "quality_score": quality_score,
                },
            )

            # Insert emails
            for email in scraped.emails:
                db.execute(
                    text("""
                        INSERT INTO lead_emails (id, lead_id, email, is_primary, is_valid)
                        VALUES (:id, :lead_id, :email, :primary, :is_valid)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "lead_id": lead_id,
                        "email": email,
                        "primary": email == scraped.emails[0],
                        "is_valid": True,
                    },
                )

            # Insert phones
            for phone in scraped.phones:
                phone_normalized = _normalize_phone_for_storage(phone)
                db.execute(
                    text("""
                        INSERT INTO lead_phones (
                            id, lead_id, phone_raw, phone_normalized, phone_type, is_primary, is_valid
                        ) VALUES (
                            :id, :lead_id, :phone, :phone_normalized, :phone_type, :primary, :is_valid
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "lead_id": lead_id,
                        "phone": phone,
                        "phone_normalized": phone_normalized,
                        "phone_type": _detect_phone_type(phone),
                        "primary": phone == scraped.phones[0],
                        "is_valid": phone_normalized is not None,
                    },
                )

            # Update progress
            total_found = leads_new + leads_duplicate
            progress = min(int(total_found / max_leads * 100), 100)
            db.execute(
                text("""
                    UPDATE extraction_jobs
                    SET progress = :progress, leads_found = :found,
                        leads_new = :new, leads_duplicate = :dup
                    WHERE id = :id
                """),
                {
                    "id": job_id,
                    "progress": progress,
                    "found": total_found,
                    "new": leads_new,
                    "dup": leads_duplicate,
                },
            )
            db.commit()

        workflow_summary = _run_post_extraction_workflows(
            db,
            organization_id=str(job["organization_id"]),
            job_id=job_id,
        )

        if workflow_summary["workflows"] > 0:
            db.execute(
                text(
                    """
                    INSERT INTO audit_logs (
                        id, organization_id, actor_user_id, action, resource_type, resource_id, details
                    ) VALUES (
                        CAST(:id AS uuid), CAST(:org_id AS uuid), NULL, 'workflow.auto_run', 'workflow', :resource_id, CAST(:details AS json)
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "org_id": str(job["organization_id"]),
                    "resource_id": job_id,
                    "details": json.dumps(
                        {
                            "trigger_event": "post_extraction",
                            "workflows": workflow_summary["workflows"],
                            "matched": workflow_summary["matched"],
                            "updated": workflow_summary["updated"],
                        }
                    ),
                },
            )

        duration_seconds = int(max(0, time.monotonic() - job_started_monotonic))
        db.execute(
            text(
                """
                INSERT INTO audit_logs (
                    id, organization_id, actor_user_id, action, resource_type, resource_id, details
                ) VALUES (
                    CAST(:id AS uuid), CAST(:org_id AS uuid), CAST(:actor_user_id AS uuid), 'extraction.analytics', 'extraction_job', :resource_id, CAST(:details AS json)
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "org_id": str(job["organization_id"]),
                "actor_user_id": str(job["created_by"]),
                "resource_id": job_id,
                "details": json.dumps(
                    {
                        "source": source,
                        "target_kind": target_kind,
                        "keywords_count": len(keywords),
                        "max_leads": max_leads,
                        "raw_scraped": raw_scraped_count,
                        "kept_after_filter": len(selected_leads),
                        "filtered_out": filter_counts["filtered_out"],
                        "classified_b2b": filter_counts["class_b2b"],
                        "classified_b2c": filter_counts["class_b2c"],
                        "classified_unknown": filter_counts["class_unknown"],
                        "with_phone": leads_with_phone,
                        "with_professional_email": leads_with_pro_email,
                        "leads_new": leads_new,
                        "leads_duplicate": leads_duplicate,
                        "duration_seconds": duration_seconds,
                        "workflows_triggered": workflow_summary["workflows"],
                        "workflow_updates": workflow_summary["updated"],
                    }
                ),
            },
        )

        # Mark job as completed
        db.execute(
            text("""
                UPDATE extraction_jobs
                SET status = 'completed', progress = 100, completed_at = :now,
                    leads_found = :found, leads_new = :new, leads_duplicate = :dup
                WHERE id = :id
            """),
            {
                "id": job_id,
                "now": datetime.now(timezone.utc),
                "found": leads_new + leads_duplicate,
                "new": leads_new,
                "dup": leads_duplicate,
            },
        )
        db.commit()

        logger.info(
            f"Job {job_id} completed: {leads_new} new, {leads_duplicate} duplicates"
        )

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        db.rollback()
        try:
            duration_seconds = int(max(0, time.monotonic() - job_started_monotonic))
            job_for_audit = (
                db.execute(
                    text(
                        "SELECT organization_id, created_by, source FROM extraction_jobs WHERE id = :id"
                    ),
                    {"id": job_id},
                )
                .mappings()
                .first()
            )
            if job_for_audit:
                try:
                    db.execute(
                        text(
                            """
                            INSERT INTO audit_logs (
                                id, organization_id, actor_user_id, action, resource_type, resource_id, details
                            ) VALUES (
                                CAST(:id AS uuid), CAST(:org_id AS uuid), CAST(:actor_user_id AS uuid), 'extraction.analytics', 'extraction_job', :resource_id, CAST(:details AS json)
                            )
                            """
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "org_id": str(job_for_audit["organization_id"]),
                            "actor_user_id": str(job_for_audit["created_by"]),
                            "resource_id": job_id,
                            "details": json.dumps(
                                {
                                    "source": job_for_audit["source"],
                                    "status": "failed",
                                    "duration_seconds": duration_seconds,
                                    "error": str(e)[:500],
                                }
                            ),
                        },
                    )
                except Exception as audit_exc:
                    logger.warning(
                        "Failed to insert extraction.analytics failure audit for job %s: %s",
                        job_id,
                        audit_exc,
                    )
            db.execute(
                text("""
                    UPDATE extraction_jobs
                    SET status = 'failed', error_message = :error, completed_at = :now
                    WHERE id = :id
                """),
                {
                    "id": job_id,
                    "error": str(e)[:500],
                    "now": datetime.now(timezone.utc),
                },
            )
            db.commit()
        except Exception:
            db.rollback()
        raise
    finally:
        db.close()
