import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.organization import Organization
from app.models.subscription import Plan, Subscription, UsageRecord
from app.schemas.subscription import PlanResponse, SubscriptionResponse, UsageResponse
from app.services.audit_log_service import AuditLogService

stripe.api_key = settings.stripe_secret_key


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _is_allowed_checkout_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False

        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False

        allowed_origins = [
            origin.strip()
            for origin in settings.checkout_allowed_origins.split(",")
            if origin.strip()
        ]

        for origin in allowed_origins:
            origin_parsed = urlparse(origin)
            if not origin_parsed.scheme:
                origin_parsed = urlparse(f"https://{origin}")

            same_scheme = parsed.scheme == origin_parsed.scheme
            same_host = parsed.hostname == origin_parsed.hostname
            same_port = (parsed.port or None) == (origin_parsed.port or None)
            if same_scheme and same_host and same_port:
                return True

        return False

    async def get_plans(self) -> list[PlanResponse]:
        result = await self.db.execute(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.monthly_price_cents)
        )
        plans = result.scalars().all()
        return [PlanResponse.model_validate(p) for p in plans]

    async def get_current(self, org_id: uuid.UUID) -> SubscriptionResponse | None:
        result = await self.db.execute(
            select(Subscription)
            .where(Subscription.organization_id == org_id, Subscription.status == "active")
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        sub = result.scalars().first()
        if not sub:
            return None
        return SubscriptionResponse.model_validate(sub)

    async def create_checkout_session(
        self, organization_id: uuid.UUID, plan_slug: str, success_url: str, cancel_url: str
    ) -> str:
        if not self._is_allowed_checkout_url(success_url):
            raise BadRequestError("Invalid success_url")
        if not self._is_allowed_checkout_url(cancel_url):
            raise BadRequestError("Invalid cancel_url")

        # Get plan
        result = await self.db.execute(select(Plan).where(Plan.slug == plan_slug))
        plan = result.scalar_one_or_none()
        if not plan:
            raise NotFoundError("Plan not found")
        if not plan.stripe_price_id:
            raise BadRequestError("Plan not configured for Stripe")

        # Get or create Stripe customer
        org_result = await self.db.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        org = org_result.scalar_one_or_none()
        if not org:
            raise NotFoundError("Organization not found")

        if not org.stripe_customer_id:
            customer = stripe.Customer.create(name=org.name, metadata={"org_id": str(org.id)})
            org.stripe_customer_id = customer.id
            await self.db.flush()

        session = stripe.checkout.Session.create(
            customer=org.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"org_id": str(organization_id), "plan_id": str(plan.id)},
        )
        await AuditLogService(self.db).log(
            action="subscription.checkout_created",
            organization_id=organization_id,
            resource_type="subscription",
            resource_id=str(plan.id),
            details={"plan_slug": plan.slug},
        )
        return session.url

    async def get_usage(self, org_id: uuid.UUID) -> UsageResponse:
        # Get current subscription's plan limits
        sub_result = await self.db.execute(
            select(Subscription)
            .where(Subscription.organization_id == org_id, Subscription.status == "active")
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        sub = sub_result.scalars().first()
        max_leads = 100  # Free tier default
        if sub and sub.plan:
            max_leads = sub.plan.max_leads_per_month

        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Count actual leads created in the current month. This is the source
        # of truth: the legacy UsageRecord table was never incremented anywhere.
        from app.models.audit_log import AuditLog
        from app.models.lead import Lead

        leads_extracted_q = (
            select(func.count())
            .select_from(Lead)
            .where(
                Lead.organization_id == org_id,
                Lead.created_at >= period_start,
            )
        )
        leads_extracted = (await self.db.execute(leads_extracted_q)).scalar() or 0

        # Exports: count audit log entries of action lead.export this month.
        exports_q = (
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.organization_id == org_id,
                AuditLog.action.in_(("lead.export", "leads.export")),
                AuditLog.created_at >= period_start,
            )
        )
        leads_exported = (await self.db.execute(exports_q)).scalar() or 0

        # Fallback: also include any legacy UsageRecord row for this period.
        legacy_q = select(UsageRecord).where(
            UsageRecord.organization_id == org_id,
            UsageRecord.period_start >= period_start,
        )
        legacy = (await self.db.execute(legacy_q)).scalar_one_or_none()
        if legacy:
            leads_extracted = max(leads_extracted, legacy.leads_extracted or 0)
            leads_exported = max(leads_exported, legacy.leads_exported or 0)

        pct = (leads_extracted / max_leads * 100) if max_leads > 0 else 0

        return UsageResponse(
            leads_extracted=int(leads_extracted),
            leads_exported=int(leads_exported),
            max_leads_per_month=max_leads,
            usage_percentage=round(pct, 1),
        )

    async def handle_stripe_webhook(self, payload: bytes, sig_header: str):
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            raise BadRequestError("Invalid webhook signature")

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            org_id = session["metadata"].get("org_id")
            plan_id = session["metadata"].get("plan_id")
            if org_id and plan_id:
                now = datetime.now(timezone.utc)
                org_uuid = uuid.UUID(org_id)
                plan_uuid = uuid.UUID(plan_id)
                stripe_sub_id = session.get("subscription")

                if stripe_sub_id:
                    existing_result = await self.db.execute(
                        select(Subscription).where(
                            Subscription.stripe_subscription_id == stripe_sub_id
                        )
                    )
                    existing = existing_result.scalars().first()
                    if existing:
                        existing.status = "active"
                        existing.plan_id = plan_uuid
                        existing.current_period_start = existing.current_period_start or now
                        await AuditLogService(self.db).log(
                            action="subscription.activated",
                            organization_id=org_uuid,
                            resource_type="subscription",
                            resource_id=str(existing.id),
                            details={"stripe_subscription_id": stripe_sub_id},
                        )
                        return

                old_active_result = await self.db.execute(
                    select(Subscription).where(
                        Subscription.organization_id == org_uuid,
                        Subscription.status == "active",
                    )
                )
                for old in old_active_result.scalars().all():
                    old.status = "canceled"
                    old.current_period_end = old.current_period_end or now

                new_sub_id = uuid.uuid4()
                new_sub = Subscription(
                    id=new_sub_id,
                    organization_id=org_uuid,
                    plan_id=plan_uuid,
                    stripe_subscription_id=stripe_sub_id,
                    status="active",
                    current_period_start=now,
                )
                self.db.add(new_sub)
                await AuditLogService(self.db).log(
                    action="subscription.activated",
                    organization_id=org_uuid,
                    resource_type="subscription",
                    resource_id=str(new_sub_id),
                    details={"stripe_subscription_id": stripe_sub_id},
                )

        elif event["type"] == "customer.subscription.deleted":
            sub_data = event["data"]["object"]
            stripe_sub_id = sub_data["id"]
            result = await self.db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = "canceled"
                await AuditLogService(self.db).log(
                    action="subscription.canceled",
                    organization_id=sub.organization_id,
                    resource_type="subscription",
                    resource_id=str(sub.id),
                    details={"stripe_subscription_id": stripe_sub_id},
                )
