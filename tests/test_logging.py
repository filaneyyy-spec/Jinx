import asyncio
import logging

import pytest
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetUpdates
from aiogram.utils.backoff import BackoffConfig

from jinx_bot.log_config import configure_logging
from tests.fakes import TelegramSession


class FailingPollingSession(TelegramSession):
    failures = 0

    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, GetUpdates):
            self.failures += 1
            if self.failures == 1:
                raise TelegramNetworkError(
                    method=method,
                    message=f"Connection failed: https://api.telegram.org/bot{bot.token}/getUpdates",
                )
            raise asyncio.CancelledError
        return await super().make_request(bot, method, timeout)


async def test_real_polling_network_errors_do_not_log_bot_token(capsys):
    token = "123456:synthetic-test-token"
    root = logging.getLogger()
    original_handlers, original_level = root.handlers[:], root.level
    session = FailingPollingSession()
    bot = Bot(token, session=session)
    try:
        configure_logging(token)
        updates = Dispatcher._listen_updates(
            bot,
            backoff_config=BackoffConfig(min_delay=0.001, max_delay=0.002, factor=1.1, jitter=0),
        )
        with pytest.raises(asyncio.CancelledError):
            await anext(updates)
        output = capsys.readouterr().err
        assert "Failed to fetch updates" in output
        assert token not in output
        assert "[REDACTED]" in output
    finally:
        await session.close()
        for handler in root.handlers:
            handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_redaction_also_covers_tracebacks_and_encoded_urls(capsys):
    token = "123456:synthetic-test-token"
    root = logging.getLogger()
    original_handlers, original_level = root.handlers[:], root.level
    try:
        configure_logging(token)
        try:
            raise RuntimeError(f"https://example.com/bot{token.replace(':', '%3A')}")
        except RuntimeError:
            logging.getLogger("aiogram.dispatcher").exception("Failure for %s", token)
        output = capsys.readouterr().err
        assert "Traceback" in output
        assert "synthetic-test-token" not in output
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)
