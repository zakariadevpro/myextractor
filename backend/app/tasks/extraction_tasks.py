from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.extraction_tasks.run_extraction", bind=True, max_retries=3)
def run_extraction(self, job_id: str):
    """Dispatch extraction job to the scraping worker.

    This task runs on the backend side and sends the actual scraping
    work to the workers service via a shared Redis broker.
    """
    from celery import current_app

    # Forward to the worker's scraping task
    current_app.send_task(
        "workers.tasks.scrape_tasks.execute_scraping",
        args=[job_id],
        queue="scraping",
    )
