from datetime import UTC, datetime

import pytest
from aiogram import Bot
from aiogram.methods import AnswerCallbackQuery, GetChatMember
from aiogram.types import Update

from jinx_bot.config import Settings
from jinx_bot.handlers import create_dispatcher
from jinx_bot.storage import Database
from tests.fakes import TelegramSession


def incoming(text="/start", *, chat_type="private", user_id=42):
    return Update.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": datetime.now(UTC),
                "chat": {"id": user_id if chat_type == "private" else -55, "type": chat_type},
                "from": {"id": user_id, "is_bot": False, "first_name": "Alice"},
                "text": text,
                "entities": [{"type": "bot_command", "offset": 0, "length": len(text)}],
            },
        }
    )


def callback(data, *, user_id=42, inline=False, chat_type="private"):
    payload = {
        "id": "callback-1",
        "from": {"id": user_id, "is_bot": False, "first_name": "Alice"},
        "chat_instance": "test-instance",
        "data": data,
    }
    if inline:
        payload["inline_message_id"] = "inline-message"
    else:
        payload["message"] = incoming(chat_type=chat_type).message.model_dump(by_alias=True)
    return Update.model_validate({"update_id": 2, "callback_query": payload})


@pytest.fixture
async def app(tmp_path):
    settings = Settings(database_path=tmp_path / "bot.sqlite3", _env_file=None)
    db = Database(settings.database_path)
    await db.initialize()
    session = TelegramSession()
    bot = Bot("123456:synthetic-test-token", session=session)
    dispatcher = create_dispatcher(settings, db)
    yield dispatcher, bot, session, db
    await bot.session.close()
    await db.close()


async def test_start_registers_user_and_shows_member_menu(app):
    dispatcher, bot, api, db = app
    await dispatcher.feed_update(bot, incoming())
    assert (await db.get_user(42)).full_name == "Alice"
    message = api.messages[-1]
    assert "Prismaxys" in message.text
    buttons = [button for row in message.reply_markup.inline_keyboard for button in row]
    assert {button.callback_data for button in buttons} >= {"subscription", "tariffs", "help"}
    assert all(button.web_app is None for button in buttons)


async def test_nonmember_cannot_open_menu_by_forging_callback(app):
    dispatcher, bot, api, _ = app
    api.member_status = "left"
    await dispatcher.feed_update(bot, callback("subscription"))
    assert "подпишитесь" in api.messages[-1].text.lower()
    buttons = [b for row in api.messages[-1].reply_markup.inline_keyboard for b in row]
    assert {button.callback_data for button in buttons} >= {"check_membership"}
    assert all(button.url is None for button in buttons)


async def test_recheck_uses_callback_sender_and_unlocks_after_joining(app):
    dispatcher, bot, api, _ = app
    api.member_status = "left"
    await dispatcher.feed_update(bot, incoming())
    api.member_status = "member"
    await dispatcher.feed_update(bot, callback("check_membership", user_id=88))
    assert "Prismaxys" in api.messages[-1].text
    checks = [call for call in api.calls if isinstance(call, GetChatMember)]
    assert checks[-1].user_id == 88
    assert checks[-1].chat_id == -1002819525144
    assert any(isinstance(call, AnswerCallbackQuery) for call in api.calls)


@pytest.mark.parametrize(
    ("status", "is_member", "allowed"),
    [
        ("creator", False, True),
        ("administrator", False, True),
        ("member", False, True),
        ("restricted", True, True),
        ("restricted", False, False),
        ("kicked", False, False),
    ],
)
async def test_membership_states(app, status, is_member, allowed):
    dispatcher, bot, api, _ = app
    api.member_status = status
    api.restricted_is_member = is_member
    await dispatcher.feed_update(bot, callback("tariffs"))
    assert ("Тарифы" in api.messages[-1].text) is allowed


async def test_membership_api_failure_does_not_unlock_or_claim_user_left(app):
    dispatcher, bot, api, _ = app
    api.fail_membership = True
    await dispatcher.feed_update(bot, incoming())
    text = api.messages[-1].text
    assert "проверить" in text.lower()
    assert "позже" in text.lower()
    assert "private API details" not in text
    assert "подпишитесь" not in text.lower()


async def test_tariffs_and_subscription_are_honest_placeholders(app):
    dispatcher, bot, api, _ = app
    for action in ["tariffs", "subscription"]:
        await dispatcher.feed_update(bot, callback(action))
        message = api.messages[-1]
        assert "—" in message.text
        buttons = [b for row in message.reply_markup.inline_keyboard for b in row]
        assert not any(button.pay or button.url for button in buttons)


async def test_membership_is_rechecked_on_later_actions(app):
    dispatcher, bot, api, _ = app
    await dispatcher.feed_update(bot, incoming())
    api.member_status = "left"
    await dispatcher.feed_update(bot, callback("tariffs"))
    assert "подпишитесь" in api.messages[-1].text.lower()


async def test_help_remains_available_when_membership_is_unavailable(app):
    dispatcher, bot, api, _ = app
    api.fail_membership = True
    await dispatcher.feed_update(bot, incoming("/help"))
    assert "Помощь" in api.messages[-1].text
    assert not any(isinstance(call, GetChatMember) for call in api.calls)


async def test_group_messages_do_not_register_users_or_show_private_menu(app):
    dispatcher, bot, api, db = app
    await dispatcher.feed_update(bot, incoming(chat_type="group"))
    assert api.messages == []
    assert await db.get_user(42) is None


@pytest.mark.parametrize("kwargs", [{"inline": True}, {"chat_type": "group"}])
async def test_nonprivate_callbacks_are_acknowledged_without_private_menu(app, kwargs):
    dispatcher, bot, api, _ = app
    await dispatcher.feed_update(bot, callback("subscription", **kwargs))
    assert api.messages == []
    assert any(isinstance(call, AnswerCallbackQuery) for call in api.calls)


async def test_configured_join_link_is_shown(tmp_path):
    settings = Settings(channel_url="https://t.me/+example", _env_file=None)
    db = Database(tmp_path / "users.sqlite3")
    await db.initialize()
    api = TelegramSession()
    api.member_status = "left"
    bot = Bot("123456:synthetic-test-token", session=api)
    try:
        await create_dispatcher(settings, db).feed_update(bot, incoming())
        buttons = [b for row in api.messages[-1].reply_markup.inline_keyboard for b in row]
        assert any(button.url == "https://t.me/+example" for button in buttons)
    finally:
        await bot.session.close()
        await db.close()


async def test_configured_mini_app_is_available_only_to_channel_members(tmp_path):
    settings = Settings(mini_app_url="https://connection.prismaxys.ru", _env_file=None)
    db = Database(tmp_path / "users.sqlite3")
    await db.initialize()
    api = TelegramSession()
    bot = Bot("123456:synthetic-test-token", session=api)
    dispatcher = create_dispatcher(settings, db)
    try:
        await dispatcher.feed_update(bot, incoming())
        buttons = [b for row in api.messages[-1].reply_markup.inline_keyboard for b in row]
        assert any(
            b.web_app and b.web_app.url == "https://connection.prismaxys.ru/" for b in buttons
        )
        api.member_status = "left"
        await dispatcher.feed_update(bot, incoming())
        buttons = [b for row in api.messages[-1].reply_markup.inline_keyboard for b in row]
        assert not any(b.web_app for b in buttons)
    finally:
        await bot.session.close()
        await db.close()


async def test_storage_failure_gives_safe_user_feedback(app):
    dispatcher, bot, api, db = app
    await db.close()
    await dispatcher.feed_update(bot, incoming())
    assert api.messages, "A storage failure should not leave the user without a response"
    assert "позже" in api.messages[-1].text.lower()
    assert "RuntimeError" not in api.messages[-1].text
