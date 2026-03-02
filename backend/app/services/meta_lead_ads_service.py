from datetime import UTC, datetime
from typing import Any

import httpx

from app.schemas.b2c import B2CLeadIntakeCreate


def _first_value(field_data: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = field_data.get(key)
        if value:
            return str(value).strip()
    return None


def _parse_field_data(rows: list[dict[str, Any]] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows or []:
        name = str(row.get("name") or "").strip().lower()
        values = row.get("values") or []
        if not name or not values:
            continue
        result[name] = str(values[0]).strip()
    return result


def _parse_meta_created_at(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(UTC)
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return datetime.now(UTC)


class MetaLeadAdsService:
    def __init__(self, access_token: str):
        self.access_token = access_token

    async def fetch_lead(self, leadgen_id: str) -> dict[str, Any]:
        url = f"https://graph.facebook.com/v21.0/{leadgen_id}"
        params = {
            "fields": "created_time,field_data,campaign_name,ad_name,ad_id,form_id,page_id",
            "access_token": self.access_token,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def build_intake_payload(
        self,
        *,
        leadgen_id: str,
        field_data_rows: list[dict[str, Any]] | None,
        created_time: str | None,
        campaign_name: str | None,
        source_channel: str = "facebook",
    ) -> B2CLeadIntakeCreate:
        fields = _parse_field_data(field_data_rows)
        first_name = _first_value(fields, ["first_name", "firstname", "prenom"])
        last_name = _first_value(fields, ["last_name", "lastname", "nom"])
        full_name = _first_value(fields, ["full_name", "name"])
        if not full_name:
            computed = " ".join(part for part in [first_name, last_name] if part).strip()
            full_name = computed or f"Meta Lead {leadgen_id}"

        email = _first_value(fields, ["email", "email_address", "courriel"])
        phone = _first_value(fields, ["phone_number", "phone", "mobile_phone"])
        city = _first_value(fields, ["city", "ville"])
        consent_text_version = _first_value(
            fields, ["consent_text_version", "consent_version", "legal_text_version"]
        ) or "meta-default"
        privacy_policy_version = _first_value(
            fields, ["privacy_policy_version", "privacy_version"]
        ) or "meta-default"
        purpose = _first_value(fields, ["purpose", "finalite"]) or "prospection_commerciale"
        doi_raw = _first_value(fields, ["double_opt_in", "doubleoptin", "doi"])
        double_opt_in = str(doi_raw or "").lower() in {"1", "true", "yes", "oui"}
        consent_at = _parse_meta_created_at(created_time)
        double_opt_in_at = consent_at if double_opt_in else None

        return B2CLeadIntakeCreate(
            full_name=full_name,
            email=email,
            phone=phone,
            city=city,
            consent_source="meta_lead_ads",
            consent_at=consent_at,
            consent_text_version=consent_text_version,
            consent_proof_ref=f"meta:{leadgen_id}",
            privacy_policy_version=privacy_policy_version,
            source_campaign=campaign_name,
            source_channel=source_channel,  # type: ignore[arg-type]
            purpose=purpose,
            double_opt_in=double_opt_in,
            double_opt_in_at=double_opt_in_at,
        )

