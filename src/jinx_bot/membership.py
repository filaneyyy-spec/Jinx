"""Channel membership is verified server-side on each protected action."""

import logging
from enum import StrEnum

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


class Membership(StrEnum):
    MEMBER = "member"
    NOT_MEMBER = "not_member"
    UNAVAILABLE = "unavailable"


async def check_membership(bot: Bot, channel_id: int, user_id: int) -> Membership:
    try:
        member = await bot.get_chat_member(channel_id, user_id)
    except TelegramAPIError as exc:
        logger.warning("Channel membership check unavailable (%s)", type(exc).__name__)
        return Membership.UNAVAILABLE
    if member.status in {"creator", "administrator", "member"}:
        return Membership.MEMBER
    if member.status == "restricted" and getattr(member, "is_member", False):
        return Membership.MEMBER
    return Membership.NOT_MEMBER
