from sqlalchemy.orm import sessionmaker

from winxtract.storage.db import create_engine_from_url, init_db
from winxtract.storage.queue_store import QueueStore


def test_queue_store_lifecycle(tmp_path):
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'queue.db'}")
    init_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    queue = QueueStore(session_factory)

    first = queue.enqueue(task_type="run", payload={"source_slug": "demo"})
    assert first.status == "queued"
    assert first.attempts == 0

    claimed = queue.claim_next(worker_id="w1")
    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status == "running"
    assert claimed.attempts == 1

    queue.mark_success(claimed.id, message="ok")
    done = queue.get_task(claimed.id)
    assert done is not None
    assert done.status == "success"
    assert done.message == "ok"


def test_queue_store_retry_then_fail(tmp_path):
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'queue_retry.db'}")
    init_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    queue = QueueStore(session_factory)

    row = queue.enqueue(task_type="run_export", payload={"source_slug": "x"}, max_attempts=2)
    first_claim = queue.claim_next(worker_id="w1")
    assert first_claim is not None
    queue.mark_failure(first_claim.id, error_message="boom-1", retry_delay_seconds=0)

    after_retry = queue.get_task(row.id)
    assert after_retry is not None
    assert after_retry.status == "queued"
    assert after_retry.attempts == 1

    second_claim = queue.claim_next(worker_id="w2")
    assert second_claim is not None
    assert second_claim.attempts == 2
    queue.mark_failure(second_claim.id, error_message="boom-2", retry_delay_seconds=0)

    terminal = queue.get_task(row.id)
    assert terminal is not None
    assert terminal.status == "dead"
    assert "boom-2" in terminal.message


def test_queue_store_update_progress(tmp_path):
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'queue_progress.db'}")
    init_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    queue = QueueStore(session_factory)

    row = queue.enqueue(task_type="run", payload={"source_slug": "demo"})
    claimed = queue.claim_next(worker_id="w1")
    assert claimed is not None

    queue.update_progress(claimed.id, "__progress__:{\"phase\":\"scrape\",\"percent\":42}")
    current = queue.get_task(row.id)
    assert current is not None
    assert current.status == "running"
    assert current.message.startswith("__progress__:")


def test_queue_store_mark_dead_and_requeue(tmp_path):
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'queue_dead.db'}")
    init_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    queue = QueueStore(session_factory)

    row = queue.enqueue(task_type="run_export", payload={"source_slug": "demo"}, max_attempts=2)
    claimed = queue.claim_next(worker_id="w1")
    assert claimed is not None

    queue.mark_dead(claimed.id, error_message="blocked")
    dead_row = queue.get_task(row.id)
    assert dead_row is not None
    assert dead_row.status == "dead"

    replay = queue.requeue_task(dead_row.id)
    assert replay is not None
    assert replay.id != dead_row.id
    assert replay.status == "queued"
    assert replay.attempts == 0
    assert replay.task_type == dead_row.task_type
    assert replay.payload == dead_row.payload
