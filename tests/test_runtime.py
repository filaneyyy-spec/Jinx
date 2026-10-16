import os
import subprocess
import sys

import pytest
from aiogram import Bot

from jinx_bot.main import StartupError, validate_telegram
from tests.fakes import TelegramSession


async def test_preflight_accepts_admin_without_webhook():
    session = TelegramSession()
    bot = Bot("123456:synthetic-test-token", session=session)
    try:
        await validate_telegram(bot, -1002819525144)
        assert {type(call).__name__ for call in session.calls} == {
            "GetMe",
            "GetWebhookInfo",
            "GetChatMember",
        }
    finally:
        await session.close()


async def test_preflight_preserves_existing_webhook():
    session = TelegramSession()
    session.webhook_url = "https://example.com/current-bot"
    bot = Bot("123456:synthetic-test-token", session=session)
    try:
        with pytest.raises(StartupError, match="webhook"):
            await validate_telegram(bot, -1002819525144)
        assert session.webhook_url == "https://example.com/current-bot"
        assert not any(type(call).__name__ == "DeleteWebhook" for call in session.calls)
    finally:
        await session.close()


async def test_preflight_requires_channel_administrator():
    session = TelegramSession()
    session.bot_is_admin = False
    bot = Bot("123456:synthetic-test-token", session=session)
    try:
        with pytest.raises(StartupError, match="администратор"):
            await validate_telegram(bot, -1002819525144)
    finally:
        await session.close()


async def test_preflight_hides_telegram_error_details():
    session = TelegramSession()
    session.fail_membership = True
    bot = Bot("123456:synthetic-test-token", session=session)
    try:
        with pytest.raises(StartupError) as caught:
            await validate_telegram(bot, -1002819525144)
        assert "private API details" not in str(caught.value)
    finally:
        await session.close()


def run_cli(tmp_path, *args, **settings):
    environment = {
        name: value for name, value in os.environ.items() if not name.startswith("JINX_")
    }
    environment.update(settings)
    return subprocess.run(
        [sys.executable, "-m", "jinx_bot", *args],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_local_check_runs_without_token_and_is_repeatable(tmp_path):
    for _ in range(2):
        result = run_cli(tmp_path, "--check")
        assert result.returncode == 0, result.stderr
        assert "Telegram не проверялся" in result.stdout
    assert (tmp_path / "data/jinx.sqlite3").exists()


def test_missing_token_fails_without_traceback(tmp_path):
    result = run_cli(tmp_path)
    assert result.returncode != 0
    assert "JINX_BOT_TOKEN" in result.stderr
    assert "Traceback" not in result.stderr


def test_invalid_token_is_not_printed(tmp_path):
    result = run_cli(tmp_path, JINX_BOT_TOKEN="a-private-invalid-token")
    assert result.returncode != 0
    assert "a-private-invalid-token" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_invalid_config_does_not_print_embedded_credentials(tmp_path):
    result = run_cli(
        tmp_path, "--check", JINX_MINI_APP_URL="https://user:private-password@example.com"
    )
    assert result.returncode != 0
    assert "private-password" not in result.stdout + result.stderr
