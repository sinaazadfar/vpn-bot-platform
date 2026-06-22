from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(alias="DATABASE_URL")
    fernet_key: str = Field(alias="FERNET_KEY")

    master_bot_token: str = Field(default="", alias="MASTER_BOT_TOKEN")
    super_user_telegram_id: int | None = Field(default=None, alias="SUPER_USER_TELEGRAM_ID")
    seller_bot_id: str | None = Field(default=None, alias="SELLER_BOT_ID")
    seller_bot_token: str = Field(default="", alias="SELLER_BOT_TOKEN")

    seller_runtime_image: str = Field(
        default="vpn-bot-platform-seller:latest",
        alias="SELLER_RUNTIME_IMAGE",
    )
    seller_docker_network: str | None = Field(default=None, alias="SELLER_DOCKER_NETWORK")
    seller_container_label_prefix: str = Field(
        default="vpn-bot-platform",
        alias="SELLER_CONTAINER_LABEL_PREFIX",
    )
    auto_start_seller_on_create: bool = Field(default=True, alias="AUTO_START_SELLER_ON_CREATE")

    marzban_token_path: str = Field(default="/api/admin/token", alias="MARZBAN_TOKEN_PATH")
    api_timeout_seconds: int = Field(default=20, alias="API_TIMEOUT_SECONDS")
    telegram_api_ip: str | None = Field(default=None, alias="TELEGRAM_API_IP")
    card_to_card_instructions: str = Field(
        default="Send the card-to-card receipt to support for approval.",
        alias="CARD_TO_CARD_INSTRUCTIONS",
    )
    marzban_default_proxies_json: str = Field(
        default='{"vless": {}}',
        alias="MARZBAN_DEFAULT_PROXIES_JSON",
    )
    trial_enabled: bool = Field(default=True, alias="TRIAL_ENABLED")
    trial_duration_days: int = Field(default=1, alias="TRIAL_DURATION_DAYS")
    trial_data_limit_gb: int = Field(default=1, alias="TRIAL_DATA_LIMIT_GB")
    bot_rate_limit_per_minute: int = Field(default=20, alias="BOT_RATE_LIMIT_PER_MINUTE")
    admin_rate_limit_per_minute: int = Field(default=10, alias="ADMIN_RATE_LIMIT_PER_MINUTE")
    admin_sensitive_rate_limit_per_minute: int = Field(
        default=5,
        alias="ADMIN_SENSITIVE_RATE_LIMIT_PER_MINUTE",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
