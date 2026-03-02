from fastapi import APIRouter

from app.api.v1.audit import router as audit_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.extractions import router as extractions_router
from app.api.v1.health import router as health_router
from app.api.v1.leads import router as leads_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.public import router as public_router
from app.api.v1.scoring import router as scoring_router
from app.api.v1.subscriptions import router as subscriptions_router
from app.api.v1.users import router as users_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.workflows import router as workflows_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(audit_router)
api_router.include_router(api_keys_router)
api_router.include_router(organizations_router)
api_router.include_router(users_router)
api_router.include_router(leads_router)
api_router.include_router(extractions_router)
api_router.include_router(dashboard_router)
api_router.include_router(scoring_router)
api_router.include_router(workflows_router)
api_router.include_router(subscriptions_router)
api_router.include_router(health_router)
api_router.include_router(webhooks_router)
api_router.include_router(public_router)
