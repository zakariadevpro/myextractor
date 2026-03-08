import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError
from app.models.lead import Lead, LeadEmail, LeadPhone
from app.models.lead_consent import LeadConsent
from app.schemas.b2c import B2CLeadIntakeCreate
from app.services.audit_log_service import AuditLogService


def _normalize_phone(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    return cleaned or None


class B2CIntakeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def intake_for_org(
        self,
        *,
        organization_id: uuid.UUID,
        data: B2CLeadIntakeCreate,
        actor_user_id: uuid.UUID | None = None,
        action: str = "lead.b2c_intake",
        source_context: str = "api",
    ) -> Lead:
        proof_result = await self.db.execute(
            select(Lead.id)
            .join(LeadConsent, LeadConsent.lead_id == Lead.id)
            .where(
                Lead.organization_id == organization_id,
                Lead.lead_kind == "b2c",
                LeadConsent.consent_source == data.consent_source,
                LeadConsent.consent_proof_ref == data.consent_proof_ref,
            )
            .limit(1)
        )
        if proof_result.scalar_one_or_none() is not None:
            raise BadRequestError("This consent proof has already been ingested")

        normalized_phone = _normalize_phone(data.phone)
        is_duplicate = False

        if data.email:
            email_dupe = await self.db.execute(
                select(Lead.id)
                .join(LeadEmail, LeadEmail.lead_id == Lead.id)
                .where(
                    Lead.organization_id == organization_id,
                    Lead.lead_kind == "b2c",
                    func.lower(LeadEmail.email) == data.email.lower(),
                )
                .limit(1)
            )
            if email_dupe.scalar_one_or_none() is not None:
                is_duplicate = True

        if normalized_phone:
            phone_dupe = await self.db.execute(
                select(Lead.id)
                .join(LeadPhone, LeadPhone.lead_id == Lead.id)
                .where(
                    Lead.organization_id == organization_id,
                    Lead.lead_kind == "b2c",
                    or_(
                        LeadPhone.phone_normalized == normalized_phone,
                        LeadPhone.phone_raw == data.phone,
                    ),
                )
                .limit(1)
            )
            if phone_dupe.scalar_one_or_none() is not None:
                is_duplicate = True

        lead = Lead(
            organization_id=organization_id,
            company_name=data.full_name.strip(),
            sector="Particulier",
            city=data.city,
            source=data.consent_source,
            lead_kind="b2c",
            is_duplicate=is_duplicate,
        )
        self.db.add(lead)
        await self.db.flush()

        if data.email:
            self.db.add(LeadEmail(lead_id=lead.id, email=data.email, is_primary=True))
        if data.phone:
            self.db.add(
                LeadPhone(
                    lead_id=lead.id,
                    phone_raw=data.phone,
                    phone_normalized=normalized_phone,
                    phone_type="mobile",
                    is_primary=True,
                )
            )

        self.db.add(
            LeadConsent(
                lead_id=lead.id,
                organization_id=organization_id,
                consent_status="granted",
                consent_scope="all",
                consent_source=data.consent_source,
                consent_at=data.consent_at,
                consent_text_version=data.consent_text_version,
                consent_proof_ref=data.consent_proof_ref,
                privacy_policy_version=data.privacy_policy_version,
                lawful_basis="consent",
                source_campaign=data.source_campaign,
                source_channel=data.source_channel,
                double_opt_in=data.double_opt_in,
                double_opt_in_at=data.double_opt_in_at,
                purpose=data.purpose,
                data_retention_until=data.data_retention_until,
            )
        )

        await self.db.flush()

        await AuditLogService(self.db).log(
            action=action,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            resource_type="lead",
            resource_id=str(lead.id),
            details={
                "lead_kind": "b2c",
                "consent_source": data.consent_source,
                "source_channel": data.source_channel,
                "source_context": source_context,
                "is_duplicate": is_duplicate,
            },
        )

        created_result = await self.db.execute(
            select(Lead)
            .options(
                selectinload(Lead.emails),
                selectinload(Lead.phones),
                selectinload(Lead.consent),
            )
            .where(Lead.id == lead.id)
        )
        return created_result.scalar_one()
