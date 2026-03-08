from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings
from app.core.security import create_access_token, decode_token


class TestSecurityTokens:
    def test_access_token_contains_active_kid_and_decodes(self, monkeypatch):
        monkeypatch.setattr(settings, "jwt_secret_key", "active-secret")
        monkeypatch.setattr(settings, "jwt_active_kid", "v1")
        monkeypatch.setattr(settings, "jwt_previous_secret_key", "")
        token = create_access_token({"sub": "user-1", "org": "org-1", "role": "admin"})

        header = jwt.get_unverified_header(token)
        assert header.get("kid") == "v1"
        payload = decode_token(token)
        assert payload is not None
        assert payload.get("sub") == "user-1"
        assert payload.get("type") == "access"

    def test_decode_accepts_previous_rotated_secret(self, monkeypatch):
        monkeypatch.setattr(settings, "jwt_secret_key", "active-secret")
        monkeypatch.setattr(settings, "jwt_active_kid", "v2")
        monkeypatch.setattr(settings, "jwt_previous_secret_key", "previous-secret")
        monkeypatch.setattr(settings, "jwt_previous_kid", "v1")
        expires = datetime.now(timezone.utc) + timedelta(minutes=5)
        token = jwt.encode(
            {"sub": "legacy-user", "type": "access", "exp": expires},
            "previous-secret",
            algorithm=settings.jwt_algorithm,
            headers={"kid": "v1"},
        )

        payload = decode_token(token)
        assert payload is not None
        assert payload.get("sub") == "legacy-user"
