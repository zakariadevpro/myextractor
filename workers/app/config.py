from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    database_url: str = "postgresql://winaity:changeme@localhost:55432/winaity"
    redis_url: str = "redis://localhost:16379/0"
    max_concurrent_browsers: int = 2
    request_delay_seconds: float = 2.0
    max_retries: int = 3
    proxy_pool_urls: str = ""
    proxy_rotation_enabled: bool = False
    b2b_strict_mode: bool = True
    website_email_enrichment_enabled: bool = True
    website_email_enrichment_max_leads: int = 50
    website_email_enrichment_max_pages_per_site: int = 4
    website_email_enrichment_timeout_seconds: float = 8.0
    website_email_enrichment_concurrency: int = 4
    contact_pro_email_bonus: int = 10
    contact_email_website_domain_match_bonus: int = 6
    contact_multi_phone_bonus: int = 4
    contact_full_profile_bonus: int = 6

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = WorkerSettings()
