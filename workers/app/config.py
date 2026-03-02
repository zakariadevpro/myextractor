from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    database_url: str = "postgresql://winaity:changeme@localhost:55432/winaity"
    redis_url: str = "redis://localhost:16379/0"
    max_concurrent_browsers: int = 2
    request_delay_seconds: float = 2.0
    max_retries: int = 3

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = WorkerSettings()
