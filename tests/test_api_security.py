from fastapi.testclient import TestClient

from winxtract.ui import create_ui_app


def test_api_token_required(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'token_test.db'}")
    monkeypatch.setenv("WINXTRACT_API_TOKEN", "secret-token")
    monkeypatch.setenv("WINXTRACT_API_RATE_LIMIT_PER_MINUTE", "100")

    app = create_ui_app()
    with TestClient(app) as client:
        no_token = client.get("/api/v1/jobs")
        assert no_token.status_code == 401

        with_token = client.get("/api/v1/jobs", headers={"X-API-Key": "secret-token"})
        assert with_token.status_code == 200


def test_api_rate_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("WINXTRACT_DB_URL", f"sqlite:///{tmp_path / 'rate_test.db'}")
    monkeypatch.setenv("WINXTRACT_API_TOKEN", "")
    monkeypatch.setenv("WINXTRACT_API_RATE_LIMIT_PER_MINUTE", "2")

    app = create_ui_app()
    with TestClient(app) as client:
        assert client.get("/api/v1/jobs").status_code == 200
        assert client.get("/api/v1/jobs").status_code == 200
        assert client.get("/api/v1/jobs").status_code == 429
