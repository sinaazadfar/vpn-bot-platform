from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    database_path: Path = Field(default=Path("data/bot.sqlite3"), alias="DATABASE_PATH")

    marzban_base_url: str = Field(default="", alias="MARZBAN_BASE_URL")
    marzban_username: str = Field(default="", alias="MARZBAN_USERNAME")
    marzban_password: str = Field(default="", alias="MARZBAN_PASSWORD")
    marzban_token: str = Field(default="", alias="MARZBAN_TOKEN")
    marzban_default_proxies_json: str = Field(default='{"vless":{},"vmess":{},"trojan":{}}', alias="MARZBAN_DEFAULT_PROXIES_JSON")

    support_text: str = Field(default="=برای اطلاعات بیشتر به پشتیبان پیام بدهید.", alias="SUPPORT_TEXT")
    tutorial_text: str = Field(default="آموزش اتصال به زودی اضافه می‌شود.", alias="TUTORIAL_TEXT")
    payment_card_text: str = Field(default="لطفا مبلغ را واریز کنید و اسکرین‌شات پرداخت را ارسال کنید.", alias="PAYMENT_CARD_TEXT")
    web_app_url: str = Field(default="", alias="WEB_APP_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def admin_ids(self) -> set[int]:
        return {int(part.strip()) for part in self.admin_ids_raw.split(",") if part.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
