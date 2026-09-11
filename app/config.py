from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str | None = None
    database_url: str = "postgresql+asyncpg://ozon:ozon@localhost:5432/ozon_prices"
    redis_url: str = "redis://localhost:6379/0"

    parser_mode: str = "auto"  # auto | api | selenium
    selenium_remote_url: str | None = None

    # If set, product parsing is delegated over HTTP to a standalone parser
    # service (app.parser_main) instead of running locally in this process.
    # Use this to run the parser on a machine with a "clean" (non-VPN) IP
    # while the bot itself runs elsewhere (e.g. behind a VPN needed for
    # Telegram access).
    parser_service_url: str | None = None
    # Shared secret sent as the X-API-Key header to the parser service, and
    # checked by the parser service against incoming requests (when set).
    parser_api_key: str | None = None

    default_percent_threshold: float = 20.0
    default_check_interval_seconds: int = 300
    priority_check_interval_seconds: int = 1
    max_concurrent_checks: int = 5
    confirm_delay_seconds: int = 3
    scheduler_tick_seconds: int = 1

    web_host: str = "0.0.0.0"
    web_port: int = 8000


settings = Settings()
