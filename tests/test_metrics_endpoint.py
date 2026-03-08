from fastapi.testclient import TestClient

from winxtract.ui import create_ui_app


def test_prometheus_metrics_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'metrics.db'}")
    app = create_ui_app()
    with TestClient(app) as client:
        resp = client.get("/metrics/prometheus")
    assert resp.status_code == 200
    body = resp.text
    assert "winxtract_leads_total" in body
    assert "winxtract_jobs_total" in body
    assert "winxtract_ui_tasks{status=\"dead\"}" in body
