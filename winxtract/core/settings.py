from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WINXTRACT_", env_file=".env")

    db_url: str = "sqlite:///./data/winxtract.db"
    log_level: str = "INFO"
    headless: bool = True
    max_pages: int = 4
    min_domain_delay: float = 1.0
    default_timeout_ms: int = 30_000
    max_retries: int = 3
    backoff_min: float = 1.0
    backoff_max: float = 10.0
    max_source_concurrency: int = 3
    privacy_mode: str = "none"
    proxy_url: str = ""
    api_token: str = ""
    api_rate_limit_per_minute: int = 120
    task_backend: str = "thread"  # thread | db_queue
    worker_poll_seconds: float = 2.0
    queue_retry_backoff_base_seconds: float = 5.0
    queue_retry_backoff_max_seconds: float = 300.0
    source_health_window_jobs: int = 10
    source_health_auto_disable_failures: int = 0
    export_required_privacy_mode: str = ""


settings = Settings()
