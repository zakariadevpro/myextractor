from typing import Any

from winxtract.core.dedupe import lead_fingerprint
from winxtract.core.models import LeadData, RawRecord
from winxtract.core.privacy import apply_particulier_conforme_policy
from winxtract.core.scoring import score_lead
from winxtract.parsers.contact import extract_emails, extract_phones
from winxtract.parsers.normalize import normalize_text


class Pipeline:
    def __init__(self, *, source_params: dict[str, Any] | None = None) -> None:
        self.source_params = source_params or {}

    def process_record(self, raw: RawRecord) -> LeadData | None:
        payload = raw.payload
        content_parts = [
            payload.get("name"),
            payload.get("city"),
            payload.get("phone"),
            payload.get("website"),
            payload.get("full_text"),
        ]
        text_blob = " ".join([part for part in content_parts if part])

        emails = extract_emails(text_blob)
        phones = extract_phones(text_blob)

        lead = LeadData(
            source_slug=raw.source_slug,
            name=normalize_text(payload.get("name")),
            city=normalize_text(payload.get("city")),
            website=normalize_text(payload.get("website")),
            phones=phones,
            emails=emails,
            description=normalize_text(payload.get("full_text")),
            address=normalize_text(payload.get("address")),
            page_url=raw.page_url,
            fingerprint=lead_fingerprint(payload.get("name"), payload.get("city"), emails),
        )
        lead = apply_particulier_conforme_policy(lead, source_params=self.source_params)
        if lead is None:
            return None
        lead.score = score_lead(lead)
        return lead
