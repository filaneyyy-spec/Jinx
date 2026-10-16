from pathlib import Path

import pytest
from pydantic import ValidationError

from jinx_bot.config import Settings


def test_defaults_do_not_invent_credentials_or_links():
    config = Settings(_env_file=None)
    assert config.channel_id == -1002819525144
    assert config.bot_token is None
    assert config.channel_url is None
    assert config.mini_app_url is None
    assert config.database_path == Path("data/jinx.sqlite3")


def test_token_is_redacted_in_settings_representation():
    config = Settings(bot_token="123456:synthetic-test-token", _env_file=None)
    assert "synthetic-test-token" not in repr(config)


@pytest.mark.parametrize(
    "url", ["http://example.com/app", "javascript:alert(1)", "https://user:secret@example.com"]
)
def test_mini_app_rejects_unsafe_urls(url):
    with pytest.raises(ValidationError):
        Settings(mini_app_url=url, _env_file=None)


def test_blank_optional_configuration_is_absent():
    config = Settings(bot_token="", channel_url="", mini_app_url="", _env_file=None)
    assert config.bot_token is None
    assert config.channel_url is None
    assert config.mini_app_url is None


def test_channel_link_must_be_a_telegram_invite_or_username():
    with pytest.raises(ValidationError):
        Settings(channel_url="https://example.com/channel", _env_file=None)
    config = Settings(channel_url="https://t.me/+test-invite", _env_file=None)
    assert str(config.channel_url) == "https://t.me/+test-invite"
