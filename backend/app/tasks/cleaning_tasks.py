import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


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
        # Create a fresh engine to avoid event loop conflicts
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
                    f"Cleaning done for org {org_id}: "
                    f"{validated} emails validated, {normalized} phones normalized, "
                    f"{deduped} duplicates marked, {scored} leads scored"
                )
        finally:
            await engine.dispose()

    _run_async(_run())
