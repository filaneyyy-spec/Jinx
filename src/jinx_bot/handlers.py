"""Private-chat menus for the initial bot release."""

import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
    WebAppInfo,
)

from jinx_bot.config import Settings
from jinx_bot.membership import Membership, check_membership
from jinx_bot.storage import Database

logger = logging.getLogger(__name__)


def keyboard(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


def action(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def menu(settings: Settings) -> InlineKeyboardMarkup:
    rows = [
        [action("🔐 Моя подписка", "subscription")],
        [action("💎 Тарифы", "tariffs"), action("💬 Помощь", "help")],
    ]
    if settings.mini_app_url:
        rows.insert(
            0,
            [
                InlineKeyboardButton(
                    text="Открыть приложение", web_app=WebAppInfo(url=str(settings.mini_app_url))
                )
            ],
        )
    return keyboard(*rows)


def create_dispatcher(settings: Settings, database: Database) -> Dispatcher:
    router = Router(name="private-menus")
    router.message.filter(F.chat.type == "private")

    async def remember(user: User) -> None:
        await database.upsert_user(user.id, user.username, user.full_name)

    async def show_help(message: Message) -> None:
        rows = []
        if settings.support_url:
            rows.append([InlineKeyboardButton(text="Написать нам", url=str(settings.support_url))])
        rows.append([action("← В меню", "menu")])
        await message.answer(
            "💬 <b>Помощь</b>\n\n"
            "Подпишитесь на наш канал и нажмите «Проверить подписку».\n"
            "В меню появятся разделы подписки и тарифов.\n\n"
            "Продажи и подключения пока не открыты. Здесь нельзя оплатить услугу "
            "или получить VPN-доступ.\n\n"
            "Начать заново: /start",
            reply_markup=keyboard(*rows),
        )

    async def show_page(message: Message, bot: Bot, user_id: int, page: str) -> None:
        status = await check_membership(bot, settings.channel_id, user_id)
        if status != Membership.MEMBER:
            rows = []
            if status == Membership.NOT_MEMBER:
                text = (
                    "👋 <b>Добро пожаловать в Prismaxys</b>\n\n"
                    "Чтобы открыть меню, подпишитесь на наш канал, "
                    "затем нажмите кнопку проверки."
                )
                if settings.channel_url:
                    rows.append(
                        [
                            InlineKeyboardButton(
                                text="Подписаться на канал", url=str(settings.channel_url)
                            )
                        ]
                    )
                else:
                    text += (
                        "\n\nСсылка на канал скоро появится. "
                        "Если вы уже участник, проверьте подписку."
                    )
            else:
                text = (
                    "Сейчас не удалось проверить подписку на канал. "
                    "Попробуйте позже — ваши данные сохранены."
                )
            rows.extend(
                [
                    [action("Проверить подписку", "check_membership")],
                    [action("Помощь", "help")],
                ]
            )
            await message.answer(text, reply_markup=keyboard(*rows))
            return
        if page == "subscription":
            text = (
                "🔐 <b>Моя подписка</b>\n\n"
                "Статус: —\nДействует до: —\nУстройства: —\n\n"
                "Выдача подключений пока не открыта. Когда сервис запустится, "
                "здесь появится ваша подписка."
            )
        elif page == "tariffs":
            text = (
                "💎 <b>Тарифы</b>\n\nЦена: —\nСрок: —\nУстройства: —\n\n"
                "Продажи ещё не открыты. Стоимость и условия появятся здесь позже."
            )
        else:
            await message.answer(
                "✦ <b>Prismaxys</b>\n\nПодписка на канал подтверждена.\nВыберите раздел ниже.",
                reply_markup=menu(settings),
            )
            return
        await message.answer(text, reply_markup=keyboard([action("← В меню", "menu")]))

    @router.message(CommandStart())
    async def start(message: Message, bot: Bot) -> None:
        if message.from_user is None:
            return
        await remember(message.from_user)
        await show_page(message, bot, message.from_user.id, "menu")

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await show_help(message)

    @router.callback_query()
    async def handle_callback(query: CallbackQuery, bot: Bot) -> None:
        if not isinstance(query.message, Message) or query.message.chat.type != "private":
            await query.answer("Откройте личный чат с ботом.")
            return
        await query.answer()
        if query.data == "help":
            await show_help(query.message)
            return
        if query.data not in {"menu", "check_membership", "subscription", "tariffs"}:
            await query.message.answer("Это меню устарело. Откройте новое: /start")
            return
        await remember(query.from_user)
        await show_page(query.message, bot, query.from_user.id, query.data)

    @router.message()
    async def unknown_message(message: Message) -> None:
        await message.answer("Откройте меню: /start\nНужна помощь: /help")

    @router.errors()
    async def on_error(event: ErrorEvent) -> bool:
        # API exception strings may contain request details. Log only the error class.
        logger.error("Update failed (%s)", type(event.exception).__name__)
        message = event.update.message
        if event.update.callback_query:
            message = event.update.callback_query.message
        if isinstance(message, Message) and message.chat.type == "private":
            try:
                await message.answer("Не удалось выполнить действие. Попробуйте позже или /start.")
            except TelegramAPIError:
                logger.warning("Could not deliver the error notification")
        return True

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher
