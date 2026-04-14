from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "Winaity Extractor"
    app_env: str = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://winaity:changeme@localhost:55432/winaity"

    # Redis
    redis_url: str = "redis://localhost:16379/0"

    # JWT
    jwt_secret_key: str = "dev-secret-key-change-me"
    jwt_active_kid: str = "v1"
    jwt_previous_secret_key: str = ""
    jwt_previous_kid: str = "v0"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Auth security
    auth_login_rate_limit: int = 10
    auth_login_window_seconds: int = 60
    auth_register_rate_limit: int = 5
    auth_register_window_seconds: int = 3600
    auth_refresh_rate_limit: int = 30
    auth_refresh_window_seconds: int = 60
    auth_cookie_mode: bool = False
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_cookie_domain: str | None = None
    auth_cookie_path: str = "/api/v1/auth"
    auth_refresh_cookie_name: str = "refresh_token"
    auth_csrf_cookie_name: str = "csrf_token"
    auth_csrf_header_name: str = "X-CSRF-Token"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = "winaity-exports"
    aws_region: str = "eu-west-3"

    # Winaity Call Center
    winaity_callcenter_webhook_url: str = ""
    winaity_callcenter_api_key: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:15173", "http://localhost:3000"]
    checkout_allowed_origins: str = "http://localhost:15173"

    # Compliance / Consent
    consent_enforcement_enabled: bool = False
    b2c_mode_enabled: bool = False
    b2c_webhook_secret: str = ""
    meta_webhook_verify_token: str = ""
    meta_access_token: str = ""

    @field_validator("jwt_secret_key", mode="after")
    @classmethod
    def check_jwt_secret(cls, value, info):
        env = info.data.get("app_env", "development")
        if env not in {"development", "dev", "test"} and value == "dev-secret-key-change-me":
            raise ValueError(
                "JWT_SECRET_KEY must be changed from default in production. "
                "Set JWT_SECRET_KEY environment variable to a strong random secret (>=32 chars)."
            )
        if env not in {"development", "dev", "test"} and len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production.")
        return value

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False

        raw = str(value).strip().lower()
        if raw in {"1", "true", "yes", "on", "debug", "dev", "development"}:
            return True
        if raw in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False

        raise ValueError(f"Invalid DEBUG value: {value}")

    @field_validator("auth_cookie_samesite", mode="before")
    @classmethod
    def parse_cookie_samesite(cls, value):
        raw = str(value or "lax").strip().lower()
        if raw not in {"lax", "strict", "none"}:
            raise ValueError(f"Invalid AUTH_COOKIE_SAMESITE value: {value}")
        return raw

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
