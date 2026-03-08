from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.subscription import (
    CheckoutRequest,
    CheckoutResponse,
    PlanResponse,
    SubscriptionResponse,
    UsageResponse,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)):
    service = SubscriptionService(db)
    return await service.get_plans()


@router.get("/current", response_model=SubscriptionResponse | None)
async def get_current_subscription(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = SubscriptionService(db)
    return await service.get_current(current_user.organization_id)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    data: CheckoutRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = SubscriptionService(db)
    url = await service.create_checkout_session(
        organization_id=current_user.organization_id,
        plan_slug=data.plan_slug,
        success_url=data.success_url,
        cancel_url=data.cancel_url,
    )
    return CheckoutResponse(checkout_url=url)


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SubscriptionService(db)
    return await service.get_usage(current_user.organization_id)


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    service = SubscriptionService(db)
    await service.handle_stripe_webhook(payload, sig_header)
    return {"status": "ok"}
