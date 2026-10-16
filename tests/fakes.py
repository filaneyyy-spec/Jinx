from datetime import UTC, datetime

from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    AnswerCallbackQuery,
    GetChatMember,
    GetMe,
    GetWebhookInfo,
    SendMessage,
)
from aiogram.types import ChatMemberMember, ChatMemberRestricted, User, WebhookInfo


class TelegramSession(BaseSession):
    """In-memory external Telegram API, while the real Dispatcher runs normally."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.member_status = "member"
        self.restricted_is_member = False
        self.fail_membership = False
        self.webhook_url = ""
        self.bot_is_admin = True
        self.closed = False

    async def close(self):
        self.closed = True

    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109 - aiogram interface
        self.calls.append(method)
        if isinstance(method, GetMe):
            return User(id=bot.id, is_bot=True, first_name="Test bot", username="test_bot")
        if isinstance(method, GetWebhookInfo):
            return WebhookInfo(
                url=self.webhook_url, has_custom_certificate=False, pending_update_count=0
            )
        if isinstance(method, GetChatMember):
            if self.fail_membership:
                raise TelegramBadRequest(method=method, message="private API details")
            user = User(id=method.user_id, is_bot=False, first_name="Test")
            status = self.member_status
            if method.user_id == bot.id:
                status = "administrator" if self.bot_is_admin else "member"
            # Telegram has many required fields for admin/restricted models.
            # model_construct preserves their actual type/status without irrelevant privileges.
            if status == "restricted":
                return ChatMemberRestricted.model_construct(
                    status=status, user=user, is_member=self.restricted_is_member
                )
            return ChatMemberMember.model_construct(status=status, user=user)
        if isinstance(method, SendMessage):
            from aiogram.types import Chat, Message

            return Message(
                message_id=len(self.calls),
                date=datetime.now(UTC),
                chat=Chat(id=int(method.chat_id), type="private"),
                text=method.text,
            ).as_(bot)
        if isinstance(method, AnswerCallbackQuery):
            return True
        raise AssertionError(f"Unexpected Telegram API method: {type(method).__name__}")

    async def stream_content(self, *args, **kwargs):
        raise AssertionError("No downloads expected")
        yield b""  # async iterator required by BaseSession

    @property
    def messages(self):
        return [call for call in self.calls if isinstance(call, SendMessage)]
