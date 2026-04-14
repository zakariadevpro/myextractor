import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.cleaning_tasks.clean_and_score_leads")
def clean_and_score_leads(org_id: str):
    """Run cleaning and scoring pipeline for an organization's leads."""
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings
    from app.services.cleaning_service import CleaningService
    from app.services.scoring_service import ScoringService

    async def _run():
        engine = create_async_engine(settings.database_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with async_session() as db:
                org_uuid = uuid.UUID(org_id)
                cleaning = CleaningService(db)
                scoring = ScoringService(db)

                validated = await cleaning.validate_emails(org_uuid)
                normalized = await cleaning.normalize_phones(org_uuid)
                deduped = await cleaning.deduplicate(org_uuid)
                scored = await scoring.score_all_unscored(org_uuid)

                await db.commit()

                logger.info(
                    "Cleaning done for org %s: "
                    "%d emails validated, %d phones normalized, "
                    "%d duplicates marked, %d leads scored",
                    org_id, validated, normalized, deduped, scored,
                )
        finally:
            await engine.dispose()

    asyncio.run(_run())


@celery_app.task(name="app.tasks.cleaning_tasks.rescore_all_leads")
def rescore_all_leads(org_id: str):
    """Rescore all leads for an organization (background task)."""
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings
    from app.services.scoring_service import ScoringService

    async def _run():
        engine = create_async_engine(settings.database_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with async_session() as db:
                org_uuid = uuid.UUID(org_id)
                scored = await ScoringService(db).rescore_all(org_uuid)
                await db.commit()
                logger.info("Rescore done for org %s: %d leads rescored", org_id, scored)
        finally:
            await engine.dispose()

    asyncio.run(_run())
