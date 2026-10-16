"""Local configuration. Runtime credentials are never stored in the repository."""

from pathlib import Path

from pydantic import HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JINX_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    bot_token: SecretStr | None = None
    channel_id: int = -1002819525144
    channel_url: HttpUrl | None = None
    mini_app_url: HttpUrl | None = None
    support_url: HttpUrl | None = None
    database_path: Path = Path("data/jinx.sqlite3")

    @field_validator("bot_token", "channel_url", "mini_app_url", "support_url", mode="before")
    @classmethod
    def empty_is_absent(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("channel_url", "mini_app_url", "support_url")
    @classmethod
    def require_https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value and (value.scheme != "https" or value.username or value.password):
            raise ValueError("URL must use HTTPS without embedded credentials")
        return value

    @field_validator("channel_url")
    @classmethod
    def require_telegram_link(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value and (value.host not in {"t.me", "telegram.me"} or value.path in {None, "/"}):
            raise ValueError("Channel URL must be a Telegram join link")
        return value
