"""
Оформление профиля бота: аватарка и описания.

При запуске бот сам ставит себе аватарку (avatar.jpg из папки проекта)
и описания. Применяется только если что-то изменилось с прошлого раза —
чтобы не дёргать Telegram при каждом перезапуске.

Чтобы сменить аватарку — замените файл avatar.jpg и перезапустите бота.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile

from config import BASE_DIR

logger = logging.getLogger(__name__)

AVATAR = BASE_DIR / "avatar.jpg"

# Текст, который ученик видит в пустом чате до нажатия «Запустить» (до 512 символов)
DESCRIPTION = (
    "💙 SchoolVoice — «Твой голос меняет школу».\n\n"
    "📝 Предлагай идеи для школы\n"
    "⚠️ Сообщай о проблемах\n"
    "🗳️ Участвуй в школьных голосованиях\n"
    "📨 Следи за ответами администрации\n\n"
    "Нажми «Запустить», чтобы начать!"
)

# Короткая строка в профиле бота (до 120 символов)
SHORT_DESCRIPTION = "Твой голос меняет школу 💙 Идеи, проблемы и голосования для учеников."


def _signature() -> str:
    h = hashlib.sha256((DESCRIPTION + "\n" + SHORT_DESCRIPTION).encode())
    if AVATAR.exists():
        h.update(AVATAR.read_bytes())
    return h.hexdigest()


async def apply_branding(bot: Bot, data_dir: Path) -> None:
    marker = data_dir / ".branding"
    signature = _signature()
    try:
        if marker.exists() and marker.read_text(encoding="utf-8").strip() == signature:
            return  # ничего не изменилось
    except OSError:
        pass

    ok = True
    try:
        await bot.set_my_description(description=DESCRIPTION)
        await bot.set_my_short_description(short_description=SHORT_DESCRIPTION)
        logger.info("Описание бота обновлено")
    except TelegramAPIError as exc:
        ok = False
        logger.warning("Не удалось обновить описание бота: %s", exc)

    if AVATAR.exists():
        try:
            from aiogram.types import InputProfilePhotoStatic  # есть в aiogram 3.24+

            await bot.set_my_profile_photo(photo=InputProfilePhotoStatic(photo=FSInputFile(AVATAR)))
            logger.info("Аватарка бота обновлена")
        except ImportError:
            ok = False
            logger.warning("Обновите aiogram (pip install -U aiogram), чтобы бот мог менять аватарку")
        except TelegramAPIError as exc:
            ok = False
            logger.warning("Не удалось обновить аватарку бота: %s", exc)

    if ok:  # при ошибке попробуем снова при следующем запуске
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text(signature, encoding="utf-8")
        except OSError:
            pass
