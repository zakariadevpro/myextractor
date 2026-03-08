from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import redis_client
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    checks = {"status": "healthy", "database": "ok", "redis": "ok"}

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"
        checks["status"] = "unhealthy"

    try:
        await redis_client.ping()
    except Exception:
        checks["redis"] = "error"
        checks["status"] = "unhealthy"

    return checks
