"""Пользовательские фильтры aiogram."""

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from config import get_settings


class IsAdmin(BaseFilter):
    """Пропускает только пользователей, чьи ID указаны в ADMIN_IDS."""

    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in get_settings().admin_ids
