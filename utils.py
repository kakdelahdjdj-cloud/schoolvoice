"""Вспомогательные функции: форматирование, безопасная отправка сообщений, уведомления."""

from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from config import get_settings
from constants import APPEAL_TYPES, CATEGORIES, STATUSES
from database import Database
from keyboards import admin_notify_kb

logger = logging.getLogger(__name__)


# ── Текст и форматирование ───────────────────────────────────────────
def h(value: Any) -> str:
    """Экранирует пользовательский текст для HTML-разметки Telegram."""
    return html.escape(str(value), quote=False)


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def one_line(text: str, limit: int = 60) -> str:
    return truncate(" ".join(text.split()), limit)


def fmt_dt(value: str | None) -> str:
    """Переводит время из БД (UTC) в часовой пояс школы."""
    if not value:
        return "—"
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return value
    return dt.astimezone(get_settings().timezone).strftime("%d.%m.%Y %H:%M")


def progress_bar(percent: float, width: int = 10) -> str:
    """Бело-голубая шкала: 🟦🟦🟦⬜⬜…"""
    filled = round(percent / 100 * width)
    return "🟦" * filled + "⬜" * (width - filled)


def validate_length(text: str, min_len: int, max_len: int) -> str | None:
    """Возвращает текст ошибки или None, если длина подходит."""
    if len(text) < min_len:
        return f"Слишком коротко: нужно минимум {min_len} символов."
    if len(text) > max_len:
        return f"Слишком длинно: максимум {max_len} символов (сейчас {len(text)})."
    return None


def is_admin(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


def format_appeal_card(appeal: dict, responses: list[dict], *, for_admin: bool = False) -> str:
    """Карточка обращения. Личные данные автора видны только администраторам и только если это разрешено."""
    lines = [f"{APPEAL_TYPES.get(appeal['type'], appeal['type'])} <b>№{appeal['id']}</b>"]
    if appeal.get("category"):
        lines.append(f"Категория: {CATEGORIES.get(appeal['category'], h(appeal['category']))}")
    lines.append(f"Статус: {STATUSES.get(appeal['status'], appeal['status'])}")
    lines.append(f"Создано: {fmt_dt(appeal['created_at'])}")
    if appeal.get("updated_at") and appeal["updated_at"] != appeal["created_at"]:
        lines.append(f"Обновлено: {fmt_dt(appeal['updated_at'])}")

    if for_admin:
        if get_settings().show_author_to_admins:
            name = h(appeal.get("full_name") or "без имени")
            username = f" (@{h(appeal['username'])})" if appeal.get("username") else ""
            lines.append(f"Автор: {name}{username} · ID <code>{appeal['user_id']}</code>")
        else:
            lines.append("Автор: 🔒 скрыт (ответ доставляется через бота)")

    lines += ["", "<b>Текст обращения:</b>", h(truncate(appeal["text"], 1500))]

    if responses:
        lines += ["", f"<b>💬 Ответы администрации ({len(responses)}):</b>"]
        if len(responses) > 3:
            lines.append("<i>Показаны последние 3.</i>")
        for r in responses[-3:]:
            lines.append(f"🔹 <i>{fmt_dt(r['created_at'])}</i>\n{h(truncate(r['text'], 400))}")
    elif not for_admin:
        lines += ["", "<i>Ответа пока нет — администрация скоро рассмотрит обращение.</i>"]
    return "\n".join(lines)


def format_poll_results(
    poll: dict, results: list[dict], user_option_id: int | None = None
) -> str:
    total = sum(r["votes"] for r in results)
    status = "🟢 Идёт голосование" if poll["is_active"] else "⏹ Голосование завершено"
    lines = [f"🗳 <b>{h(poll['question'])}</b>", status, ""]
    for i, r in enumerate(results, start=1):
        percent = (r["votes"] / total * 100) if total else 0
        mark = " ✅" if r["id"] == user_option_id else ""
        lines.append(f"{i}. {h(r['text'])}{mark} — <b>{r['votes']}</b> ({percent:.0f}%)")
        lines.append(progress_bar(percent))
    lines += ["", f"Всего голосов: <b>{total}</b>"]
    if user_option_id is not None:
        lines.append("✅ — ваш голос")
    return "\n".join(lines)


# ── Работа с сообщениями ─────────────────────────────────────────────
async def callback_message(cb: CallbackQuery) -> Message | None:
    """Возвращает сообщение с кнопкой или сообщает пользователю, что оно устарело."""
    if isinstance(cb.message, Message):
        return cb.message
    await cb.answer("Сообщение устарело. Откройте раздел заново из меню.", show_alert=True)
    return None


async def safe_edit(message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Редактирует сообщение; если это невозможно — отправляет новое."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        logger.debug("Не удалось отредактировать сообщение: %s", exc)
        await message.answer(text, reply_markup=reply_markup)


async def safe_send(
    bot: Bot, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> bool:
    """Отправляет сообщение, не падая, если пользователь заблокировал бота."""
    for attempt in range(2):
        try:
            await bot.send_message(chat_id, text, reply_markup=reply_markup)
            return True
        except TelegramRetryAfter as exc:
            if attempt == 0:
                await asyncio.sleep(exc.retry_after)
                continue
            logger.warning("Флуд-лимит при отправке %s", chat_id)
        except TelegramForbiddenError:
            logger.info("Пользователь %s заблокировал бота", chat_id)
        except TelegramBadRequest as exc:
            logger.warning("Не удалось отправить сообщение %s: %s", chat_id, exc)
        except TelegramAPIError as exc:
            logger.error("Ошибка Telegram API при отправке %s: %s", chat_id, exc)
        return False
    return False


async def broadcast(
    bot: Bot, user_ids: Iterable[int], text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> tuple[int, int]:
    """Рассылка с паузой между сообщениями (лимиты Telegram). Возвращает (доставлено, ошибок)."""
    sent = failed = 0
    for uid in user_ids:
        if await safe_send(bot, uid, text, reply_markup):
            sent += 1
        else:
            failed += 1
        await asyncio.sleep(0.05)
    return sent, failed


async def notify_admins(bot: Bot, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    for admin_id in get_settings().admin_ids:
        await safe_send(bot, admin_id, text, reply_markup)


async def appeal_limit_reached(db: Database, user_id: int) -> bool:
    """Антиспам: не больше MAX_APPEALS_PER_DAY обращений за 24 часа (0 — без ограничений)."""
    limit = get_settings().max_appeals_per_day
    if limit == 0:
        return False
    return await db.count_recent_appeals(user_id) >= limit


def limit_message() -> str:
    limit = get_settings().max_appeals_per_day
    return (
        f"⏳ Вы уже отправили {limit} обращений за последние 24 часа. "
        "Пожалуйста, попробуйте позже — так мы защищаемся от спама."
    )


async def submit_appeal(
    db: Database, bot: Bot, user_id: int, appeal_type: str, text: str, category: str | None = None
) -> int:
    """Сохраняет обращение и уведомляет администраторов (без личных данных автора)."""
    appeal_id = await db.create_appeal(user_id, appeal_type, text, category)
    header = f"🔔 <b>Новое обращение №{appeal_id}</b>\n{APPEAL_TYPES[appeal_type]}"
    if category:
        header += f" · {CATEGORIES.get(category, category)}"
    await notify_admins(bot, f"{header}\n\n{h(truncate(text, 700))}", admin_notify_kb(appeal_id))
    logger.info("Создано обращение №%s (%s)", appeal_id, appeal_type)
    return appeal_id
