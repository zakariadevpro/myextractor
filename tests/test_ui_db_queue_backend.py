from fastapi.testclient import TestClient

from winxtract.ui import create_ui_app


def test_ui_actions_enqueue_in_db_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'ui_queue.db'}")
    monkeypatch.setenv("WINXTRACT_TASK_BACKEND", "db_queue")

    app = create_ui_app()
    with TestClient(app) as client:
        resp = client.post("/api/v1/actions/run", json={"source_slug": "demo"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        task_id = body["task_id"]

        tasks = client.get("/api/v1/tasks")
        assert tasks.status_code == 200
        assert tasks.json()["backend"] == "db_queue"
        assert "progress_percent" in tasks.json()["items"][0]
        assert "progress_label" in tasks.json()["items"][0]

        detail = client.get(f"/api/v1/tasks/{task_id}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["id"] == str(task_id)
        assert data["type"] == "run"
        assert data["status"] == "queued"
        assert "progress_percent" in data
        assert "progress_label" in data


def test_onboarding_page_and_redirect(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'ui_onboarding.db'}")
    monkeypatch.setenv("WINXTRACT_TASK_BACKEND", "db_queue")

    app = create_ui_app()
    with TestClient(app) as client:
        page = client.get("/onboarding")
        assert page.status_code == 200
        assert "Onboarding" in page.text

        action = client.post(
            "/run",
            data={"source_slug": "__missing__", "next_page": "/onboarding"},
            follow_redirects=False,
        )
        assert action.status_code == 303
        assert action.headers["location"].startswith("/onboarding?msg=")


def test_ui_action_run_export_all_enqueues(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'ui_run_export_all.db'}")
    monkeypatch.setenv("WINXTRACT_TASK_BACKEND", "db_queue")

    app = create_ui_app()
    with TestClient(app) as client:
        resp = client.post("/api/v1/actions/run-export-all", json={"export_format": "csv", "min_score": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"

        task_id = body["task_id"]
        detail = client.get(f"/api/v1/tasks/{task_id}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["id"] == str(task_id)
        assert data["type"] == "run_export_all"
        assert data["status"] == "queued"
