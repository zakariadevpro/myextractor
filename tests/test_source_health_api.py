from fastapi.testclient import TestClient

from winxtract.ui import create_ui_app


def test_source_health_api(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'source_health_api.db'}")
    app = create_ui_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/source-health")
    assert resp.status_code == 200
    body = resp.json()
    assert "sources_count" in body
    assert "items" in body
