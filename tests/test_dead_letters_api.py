from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from winxtract.storage.db import create_engine_from_url, init_db
from winxtract.storage.queue_store import QueueStore
from winxtract.ui import create_ui_app


def test_dead_letters_page_and_requeue_api(monkeypatch, tmp_path):
    db_url = f"sqlite:///{tmp_path / 'dead_letters.db'}"
    monkeypatch.setenv("WINXTRACT_DB_URL", db_url)
    monkeypatch.setenv("WINXTRACT_TASK_BACKEND", "db_queue")

    app = create_ui_app()
    engine = create_engine_from_url(db_url)
    init_db(engine)
    queue = QueueStore(sessionmaker(bind=engine, expire_on_commit=False))

    row = queue.enqueue(task_type="run", payload={"source_slug": "demo"})
    claimed = queue.claim_next(worker_id="w1")
    assert claimed is not None
    queue.mark_dead(claimed.id, error_message="anti-bot blocked")

    second = queue.enqueue(task_type="run_export", payload={"source_slug": "other"})
    claimed_second = queue.claim_next(worker_id="w2")
    assert claimed_second is not None
    queue.mark_dead(claimed_second.id, error_message="temporary timeout")

    with TestClient(app) as client:
        page = client.get("/dead-letters")
        assert page.status_code == 200
        assert "Dead Letters" in page.text

        tasks = client.get("/api/v1/tasks", params={"status": "dead"})
        assert tasks.status_code == 200
        assert tasks.json()["count"] >= 1

        replay = client.post(f"/api/v1/tasks/{row.id}/requeue")
        assert replay.status_code == 200
        payload = replay.json()
        assert payload["status"] == "queued"
        assert payload["requeued_from"] == str(row.id)

        filtered = client.get(
            "/api/v1/dead-letters",
            params={"status": "dead", "source_slug": "other", "limit": 50},
        )
        assert filtered.status_code == 200
        assert filtered.json()["count"] == 1
        assert filtered.json()["items"][0]["id"] == str(second.id)

        batch = client.post(
            "/api/v1/tasks/requeue-batch",
            json={"status": "dead", "source_slug": "other", "limit": 50},
        )
        assert batch.status_code == 200
        assert batch.json()["requeued_count"] == 1

        batch_ui = client.post(
            "/tasks/requeue-batch",
            data={
                "status": "dead",
                "task_type": "run_export",
                "source_slug": "other",
                "message_contains": "",
                "limit": "50",
                "next_page": "/dead-letters",
            },
            follow_redirects=False,
        )
        assert batch_ui.status_code == 303
        assert batch_ui.headers["location"].startswith("/dead-letters?msg=")


def test_requeue_api_not_available_in_thread_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'dead_letters_thread.db'}")
    monkeypatch.setenv("WINXTRACT_TASK_BACKEND", "thread")
    app = create_ui_app()

    with TestClient(app) as client:
        resp = client.post("/api/v1/tasks/1/requeue")
    assert resp.status_code == 400

    with TestClient(app) as client:
        resp_batch = client.post("/api/v1/tasks/requeue-batch", json={"status": "dead"})
    assert resp_batch.status_code == 400
