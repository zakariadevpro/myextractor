from celery import Celery

from app.config import settings

celery_app = Celery(
    "winaity",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.extraction_tasks",
        "app.tasks.cleaning_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    task_routes={
        "app.tasks.extraction_tasks.*": {"queue": "default"},
        "app.tasks.cleaning_tasks.*": {"queue": "cleaning"},
    },
    task_default_queue="default",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
