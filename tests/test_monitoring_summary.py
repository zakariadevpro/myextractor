from fastapi.testclient import TestClient

from winxtract.ui import create_ui_app


def test_monitoring_summary_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'monitoring.db'}")
    app = create_ui_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/monitoring/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "metrics" in body
    assert "source_health" in body
    assert "task_backend" in body["metrics"]
    assert "dead" in body["metrics"]["task_status"]


def test_source_health_page(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'monitoring_page.db'}")
    app = create_ui_app()
    with TestClient(app) as client:
        resp = client.get("/source-health")
    assert resp.status_code == 200
    assert "Source Health" in resp.text
