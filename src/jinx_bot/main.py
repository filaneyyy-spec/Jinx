"""CLI and non-destructive Telegram startup checks."""

import argparse
import asyncio
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError
from aiogram.utils.token import TokenValidationError, validate_token
from pydantic import ValidationError

from jinx_bot.config import Settings
from jinx_bot.handlers import create_dispatcher
from jinx_bot.log_config import configure_logging
from jinx_bot.storage import Database


class StartupError(Exception):
    """A safe, actionable startup message, without request or credential details."""


async def validate_telegram(bot: Bot, channel_id: int) -> None:
    try:
        identity = await bot.get_me()
        webhook = await bot.get_webhook_info()
        if webhook.url:
            raise StartupError(
                "У бота настроен webhook. Сначала согласуйте переключение на polling; "
                "существующий webhook не изменён."
            )
        membership = await bot.get_chat_member(channel_id, identity.id)
        if membership.status not in {"administrator", "creator"}:
            raise StartupError("Добавьте бота администратором настроенного канала.")
    except TelegramAPIError as exc:
        raise StartupError(
            "Не удалось проверить Telegram. Проверьте токен, доступ к сети, ID канала и права бота."
        ) from exc


async def run(settings: Settings, *, check_only: bool) -> None:
    token = settings.bot_token.get_secret_value() if settings.bot_token else None
    if token:
        try:
            validate_token(token)
        except TokenValidationError as exc:
            raise StartupError("Неверный формат JINX_BOT_TOKEN.") from exc
    elif not check_only:
        raise StartupError("Укажите JINX_BOT_TOKEN в окружении или локальном .env.")

    database = Database(settings.database_path)
    bot = None
    try:
        await database.initialize()
        if check_only:
            print("Настройки и база проверены. Telegram не проверялся; polling не запущен.")
            return
        bot = Bot(token, default=DefaultBotProperties(parse_mode="HTML"))
        await validate_telegram(bot, settings.channel_id)
        dispatcher = create_dispatcher(settings, database)
        await dispatcher.start_polling(
            bot, allowed_updates=dispatcher.resolve_used_update_types(), close_bot_session=False
        )
    finally:
        if bot:
            await bot.session.close()
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prismaxys Telegram bot")
    parser.add_argument(
        "--check", action="store_true", help="Проверить настройки и SQLite без сети"
    )
    arguments = parser.parse_args()
    try:
        settings = Settings()
        configure_logging(settings.bot_token.get_secret_value() if settings.bot_token else None)
        asyncio.run(run(settings, check_only=arguments.check))
    except ValidationError as exc:
        fields = sorted({str(error["loc"][0]) for error in exc.errors(include_input=False)})
        print("Неверная конфигурация: " + ", ".join(fields), file=sys.stderr)
        raise SystemExit(2) from None
    except StartupError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        # Do not print third-party exceptions: they can include tokens or request URLs.
        print(f"Не удалось запустить бота ({type(exc).__name__}).", file=sys.stderr)
        raise SystemExit(1) from None
