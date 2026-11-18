"""
SchoolVoice — Telegram-бот «Твой голос меняет школу».

Точка входа: python main.py
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from branding import apply_branding
from config import ConfigError, Settings, get_settings
from database import Database
from handlers import get_routers
from middlewares import UserMiddleware

logger = logging.getLogger("schoolvoice")


async def on_error(event: ErrorEvent) -> bool:
    """Глобальный обработчик ошибок: пишет в лог и вежливо сообщает пользователю."""
    logger.exception("Ошибка при обработке апдейта: %s", event.exception, exc_info=event.exception)
    update = event.update
    try:
        if update.message:
            await update.message.answer("⚠️ Произошла ошибка. Попробуйте ещё раз или отправьте /start.")
        elif update.callback_query:
            await update.callback_query.answer("⚠️ Произошла ошибка. Попробуйте ещё раз.", show_alert=True)
    except Exception:  # не даём ошибке в обработчике ошибок уронить бота
        logger.debug("Не удалось уведомить пользователя об ошибке", exc_info=True)
    return True


def build_dispatcher(db: Database, settings: Settings) -> Dispatcher:
    """Собирает диспетчер: хранилище состояний, зависимости, middleware, роутеры."""
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db              # доступно в обработчиках как аргумент db
    dp["settings"] = settings  # доступно как аргумент settings

    # Бот работает только в личных сообщениях — так данные учеников не видны в группах
    dp.message.filter(F.chat.type == ChatType.PRIVATE)
    dp.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

    user_mw = UserMiddleware(db)
    dp.message.outer_middleware(user_mw)
    dp.callback_query.outer_middleware(user_mw)

    dp.include_routers(*get_routers())
    dp.errors.register(on_error)
    return dp


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="help", description="Как пользоваться ботом"),
            BotCommand(command="about", description="О проекте"),
            BotCommand(command="cancel", description="Отменить текущее действие"),
        ]
    )


async def main() -> None:
    try:
        settings = get_settings()
    except ConfigError as exc:
        print(f"❌ Ошибка настройки: {exc}", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    if not settings.admin_ids:
        logger.warning("ADMIN_IDS не задан — панель администрации никому не доступна.")

    db = Database(settings.db_path)
    await db.init()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(db, settings)

    try:
        me = await bot.get_me()
        logger.info("Бот @%s запущен. Администраторов: %d", me.username, len(settings.admin_ids))
        await set_bot_commands(bot)
        await apply_branding(bot, settings.db_path.parent)  # аватарка и описание
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except TelegramUnauthorizedError:
        logger.error("Telegram отклонил токен. Проверьте BOT_TOKEN в файле .env.")
        sys.exit(1)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code not in (None, 0):
            raise
        print("Бот остановлен.")
