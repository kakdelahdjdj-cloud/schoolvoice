"""Middleware: регистрация пользователей в базе данных."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from database import Database

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    """Перед каждым сообщением/нажатием сохраняет (или обновляет) пользователя в БД."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is not None and not user.is_bot:
            try:
                await self.db.upsert_user(user.id, user.username, user.full_name)
            except Exception:  # ошибка БД не должна ломать обработку сообщения
                logger.exception("Не удалось сохранить пользователя %s", user.id)
        return await handler(event, data)
