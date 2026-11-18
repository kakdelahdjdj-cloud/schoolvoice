"""
🛠 Кабинет администрации.

Доступ только для ID из ADMIN_IDS: фильтр IsAdmin стоит на всём роутере,
поэтому ни одно сообщение или нажатие от обычного пользователя сюда не попадёт.
"""

from __future__ import annotations

import math
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from callbacks import AdmAppealCB, AdmListCB, AdmMenuCB, AdmPollCB, ConfirmCB
from constants import (
    ADMIN_PAGE_SIZE,
    ADMIN_POLLS_LIMIT,
    APPEAL_TYPES,
    BTN_ADMIN,
    CATEGORIES,
    MENU_BUTTONS,
    POLL_OPTION_MAX_LEN,
    POLL_OPTIONS_MAX,
    POLL_OPTIONS_MIN,
    POLL_QUESTION_MAX,
    POLL_QUESTION_MIN,
    REPLY_MAX_LEN,
    REPLY_MIN_LEN,
    STATUS_EMOJI,
    STATUS_PENDING,
    STATUS_PROGRESS,
    STATUS_RESOLVED,
    STATUSES,
    TYPE_CODES,
    TYPE_PROBLEM,
    TYPE_SUGGESTION,
)
from database import Database
from filters import IsAdmin
from keyboards import (
    admin_appeal_kb,
    admin_delete_confirm_kb,
    admin_list_kb,
    admin_menu_kb,
    admin_poll_delete_kb,
    admin_poll_kb,
    admin_polls_kb,
    back_to_admin_kb,
    cancel_kb,
    main_menu,
    poll_create_confirm_kb,
    poll_invite_kb,
    user_appeal_open_kb,
)
from states import AdminStates
from utils import (
    broadcast,
    callback_message,
    fmt_dt,
    format_appeal_card,
    format_poll_results,
    h,
    one_line,
    safe_edit,
    safe_send,
    validate_length,
)

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

ADMIN_HOME = (
    "🛠 <b>Кабинет администрации SchoolVoice</b>\n\n"
    "📥 Просмотр обращений и ответы ученикам\n"
    "🔄 Изменение статусов\n"
    "🗳 Создание и управление голосованиями\n"
    "📊 Подробная статистика\n\n"
    "Выберите раздел:"
)

DEFAULT_FILTER = {"t": "a", "st": "all", "page": 0}
LIST_TITLES = {"a": "📥 Все обращения", "s": "💡 Предложения", "p": "⚠️ Проблемы"}


# ── Вспомогательные функции ──────────────────────────────────────────
async def _list_filter(state: FSMContext) -> dict:
    """Последний открытый фильтр списка (чтобы «⬅️ К списку» возвращал туда же)."""
    return (await state.get_data()).get("adm_list") or DEFAULT_FILTER


async def build_appeals_list(db: Database, t: str, st: str, page: int) -> tuple[str, InlineKeyboardMarkup, int]:
    appeal_type = TYPE_CODES.get(t)
    status = st if st in STATUSES else None
    total = await db.count_appeals(appeal_type, status)
    pages = max(1, math.ceil(total / ADMIN_PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    appeals = await db.list_appeals(appeal_type, status, ADMIN_PAGE_SIZE, page * ADMIN_PAGE_SIZE)

    filter_label = STATUSES[status] if status else "все статусы"
    lines = [f"<b>{LIST_TITLES.get(t, LIST_TITLES['a'])}</b> · {filter_label}", f"Найдено: {total}", ""]
    if not appeals:
        lines.append("<i>Обращений нет.</i>")
    for a in appeals:
        extra = f" · {CATEGORIES.get(a['category'], '')}" if a.get("category") else ""
        lines.append(
            f"{STATUS_EMOJI.get(a['status'], '•')} <b>№{a['id']}</b> · {APPEAL_TYPES[a['type']]}{extra} · "
            f"{fmt_dt(a['created_at'])}\n<i>{h(one_line(a['text'], 70))}</i>"
        )
    return "\n".join(lines), admin_list_kb(appeals, t, st, page, pages), page


async def render_appeal(db: Database, state: FSMContext, appeal_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    appeal = await db.get_appeal(appeal_id)
    if appeal is None:
        return None
    responses = await db.get_responses(appeal_id)
    text = format_appeal_card(appeal, responses, for_admin=True)
    return text, admin_appeal_kb(appeal, await _list_filter(state))


async def show_list(
    cb: CallbackQuery, state: FSMContext, db: Database, t: str, st: str, page: int, notice: str | None = None
) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    text, kb, page = await build_appeals_list(db, t, st, page)
    await state.update_data(adm_list={"t": t, "st": st, "page": page})
    await safe_edit(msg, text, kb)
    await cb.answer(notice)


async def build_admin_polls(db: Database) -> tuple[str, InlineKeyboardMarkup]:
    polls = await db.list_polls(limit=ADMIN_POLLS_LIMIT)
    text = "🗂 <b>Управление голосованиями</b>\n\n"
    text += (
        "🟢 — активно, ⏹ — завершено. Число справа — количество голосов.\nВыберите голосование:"
        if polls
        else "Голосований пока нет."
    )
    return text, admin_polls_kb(polls)


async def render_admin_poll(db: Database, poll_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    poll = await db.get_poll(poll_id)
    if poll is None:
        return None
    results = await db.get_poll_results(poll_id)
    text = format_poll_results(poll, results)
    text += f"\n\n<i>№{poll['id']} · создано {fmt_dt(poll['created_at'])}</i>"
    if poll["closed_at"]:
        text += f"\n<i>завершено {fmt_dt(poll['closed_at'])}</i>"
    return text, admin_poll_kb(poll)


def format_admin_stats(s: dict) -> str:
    lines = [
        "📊 <b>Подробная статистика</b>",
        "",
        f"👥 Пользователей: <b>{s['users']}</b>",
        "",
        f"📬 Обращений всего: <b>{s['appeals_total']}</b>",
        f"   за сегодня: {s['appeals_today']} · за 7 дней: {s['appeals_week']}",
        f"   💡 Предложений: {s['by_type'].get(TYPE_SUGGESTION, 0)}",
        f"   ⚠️ Проблем: {s['by_type'].get(TYPE_PROBLEM, 0)}",
        "",
        "<b>По статусам:</b>",
        f"🟡 На рассмотрении: {s['by_status'].get(STATUS_PENDING, 0)}",
        f"🔵 В обработке: {s['by_status'].get(STATUS_PROGRESS, 0)}",
        f"🟢 Решено: {s['by_status'].get(STATUS_RESOLVED, 0)}",
        "",
        "<b>Проблемы по категориям:</b>",
    ]
    for code, title in CATEGORIES.items():
        lines.append(f"{title}: {s['by_category'].get(code, 0)}")
    lines += [
        "",
        f"💬 Ответов администрации: {s['responses']}",
        f"🗳 Голосований: {s['polls_total']} (активных: {s['polls_active']})",
        f"✋ Голосов: {s['votes_total']}",
    ]
    return "\n".join(lines)


def parse_poll_options(raw: str) -> list[str]:
    """Каждая строка — вариант. Убираем маркеры списка: «-», «•», «1.», «2)»."""
    options = []
    for line in raw.splitlines():
        line = re.sub(r"^\s*(?:[-•*—]|\d+[.)])\s*", "", line).strip()
        if line:
            options.append(line)
    return options


# ── Вход в панель ────────────────────────────────────────────────────
@router.message(Command("admin"))
@router.message(F.text == BTN_ADMIN)
async def admin_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(ADMIN_HOME, reply_markup=admin_menu_kb())


@router.callback_query(AdmMenuCB.filter(F.section == "home"))
async def admin_home(cb: CallbackQuery, state: FSMContext) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    await state.set_state(None)
    await safe_edit(msg, ADMIN_HOME, admin_menu_kb())
    await cb.answer()


# ── Обращения ────────────────────────────────────────────────────────
@router.callback_query(AdmMenuCB.filter(F.section.in_({"all", "sug", "prb"})))
async def admin_sections(cb: CallbackQuery, callback_data: AdmMenuCB, state: FSMContext, db: Database) -> None:
    t = {"all": "a", "sug": "s", "prb": "p"}[callback_data.section]
    await show_list(cb, state, db, t, "all", 0)


@router.callback_query(AdmListCB.filter())
async def admin_list(cb: CallbackQuery, callback_data: AdmListCB, state: FSMContext, db: Database) -> None:
    await show_list(cb, state, db, callback_data.t, callback_data.st, callback_data.page)


@router.callback_query(AdmAppealCB.filter(F.action == "view"))
async def admin_view_appeal(cb: CallbackQuery, callback_data: AdmAppealCB, state: FSMContext, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    view = await render_appeal(db, state, callback_data.appeal_id)
    if view is None:
        await cb.answer("Обращение не найдено (возможно, удалено).", show_alert=True)
        return
    await safe_edit(msg, *view)
    await cb.answer()


@router.callback_query(AdmAppealCB.filter(F.action == "st"))
async def admin_set_status(
    cb: CallbackQuery, callback_data: AdmAppealCB, state: FSMContext, db: Database, bot: Bot
) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    new_status = callback_data.value
    if new_status not in STATUSES:
        await cb.answer("Неизвестный статус.", show_alert=True)
        return
    appeal = await db.get_appeal(callback_data.appeal_id)
    if appeal is None:
        await cb.answer("Обращение не найдено.", show_alert=True)
        return
    if appeal["status"] == new_status:
        await cb.answer("Этот статус уже установлен.")
        return

    await db.update_appeal_status(appeal["id"], new_status)
    # Сообщаем автору об изменении статуса
    await safe_send(
        bot,
        appeal["user_id"],
        f"🔔 Статус вашего обращения <b>№{appeal['id']}</b> изменён:\n{STATUSES[new_status]}",
        user_appeal_open_kb(appeal["id"]),
    )
    view = await render_appeal(db, state, appeal["id"])
    if view:
        await safe_edit(msg, *view)
    await cb.answer(f"Статус: {STATUSES[new_status]}")


@router.callback_query(AdmAppealCB.filter(F.action == "reply"))
async def admin_reply_start(cb: CallbackQuery, callback_data: AdmAppealCB, state: FSMContext, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    if await db.get_appeal(callback_data.appeal_id) is None:
        await cb.answer("Обращение не найдено.", show_alert=True)
        return
    await state.set_state(AdminStates.reply_text)
    await state.update_data(reply_appeal_id=callback_data.appeal_id)
    await msg.answer(
        f"✍️ Напишите ответ на обращение <b>№{callback_data.appeal_id}</b> одним сообщением.\n"
        "Ученик получит его от имени администрации (ваше имя не показывается).",
        reply_markup=cancel_kb(),
    )
    await cb.answer()


@router.message(AdminStates.reply_text, F.text, ~F.text.in_(MENU_BUTTONS))
async def admin_reply_text(message: Message, state: FSMContext, db: Database, bot: Bot) -> None:
    text = message.text.strip()
    if error := validate_length(text, REPLY_MIN_LEN, REPLY_MAX_LEN):
        await message.answer(f"⚠️ {error}")
        return
    appeal_id = (await state.get_data()).get("reply_appeal_id")
    appeal = await db.get_appeal(appeal_id) if appeal_id else None
    await state.set_state(None)
    await state.update_data(reply_appeal_id=None)
    if appeal is None:
        await message.answer("Обращение не найдено (возможно, удалено).", reply_markup=main_menu(True))
        return

    await db.add_response(appeal["id"], message.from_user.id, text)
    status = appeal["status"]
    if status == STATUS_PENDING:
        # Получив ответ, обращение автоматически переходит «В обработку»
        status = STATUS_PROGRESS
        await db.update_appeal_status(appeal["id"], status)

    delivered = await safe_send(
        bot,
        appeal["user_id"],
        f"📩 <b>Ответ администрации</b> на ваше обращение №{appeal['id']}:\n\n{h(text)}\n\n"
        f"Статус: {STATUSES[status]}",
        user_appeal_open_kb(appeal["id"]),
    )
    note = (
        "✅ Ответ сохранён и отправлен ученику."
        if delivered
        else "✅ Ответ сохранён, но доставить его не удалось (ученик, вероятно, остановил бота). "
        "Он увидит ответ в разделе «Мои обращения»."
    )
    await message.answer(note, reply_markup=main_menu(True))
    view = await render_appeal(db, state, appeal["id"])
    if view:
        await message.answer(view[0], reply_markup=view[1])


@router.callback_query(AdmAppealCB.filter(F.action == "del"))
async def admin_delete_ask(cb: CallbackQuery, callback_data: AdmAppealCB) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    await safe_edit(
        msg,
        f"🗑 Удалить обращение <b>№{callback_data.appeal_id}</b> вместе с ответами?\nЭто действие нельзя отменить.",
        admin_delete_confirm_kb(callback_data.appeal_id),
    )
    await cb.answer()


@router.callback_query(AdmAppealCB.filter(F.action == "delok"))
async def admin_delete_confirm(cb: CallbackQuery, callback_data: AdmAppealCB, state: FSMContext, db: Database) -> None:
    deleted = await db.delete_appeal(callback_data.appeal_id)
    f = await _list_filter(state)
    notice = f"Обращение №{callback_data.appeal_id} удалено." if deleted else "Обращение уже удалено."
    await show_list(cb, state, db, f["t"], f["st"], f["page"], notice)


# ── Создание голосования ─────────────────────────────────────────────
@router.callback_query(AdmMenuCB.filter(F.section == "newpoll"))
async def admin_new_poll(cb: CallbackQuery, state: FSMContext) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    await state.set_state(AdminStates.poll_question)
    await msg.answer(
        "🗳 <b>Новое голосование</b>\n\n"
        f"Шаг 1 из 2. Отправьте вопрос ({POLL_QUESTION_MIN}–{POLL_QUESTION_MAX} символов).\n"
        "Например: <i>Какой кружок открыть в следующей четверти?</i>",
        reply_markup=cancel_kb(),
    )
    await cb.answer()


@router.message(AdminStates.poll_question, F.text, ~F.text.in_(MENU_BUTTONS))
async def admin_poll_question(message: Message, state: FSMContext) -> None:
    question = message.text.strip()
    if error := validate_length(question, POLL_QUESTION_MIN, POLL_QUESTION_MAX):
        await message.answer(f"⚠️ {error}")
        return
    await state.update_data(poll_question=question)
    await state.set_state(AdminStates.poll_options)
    await message.answer(
        "Шаг 2 из 2. Отправьте варианты ответа — <b>каждый с новой строки</b> "
        f"(от {POLL_OPTIONS_MIN} до {POLL_OPTIONS_MAX}, до {POLL_OPTION_MAX_LEN} символов каждый).\n\n"
        "Например:\n<code>Робототехника\nШахматы\nТеатральный кружок</code>"
    )


@router.message(AdminStates.poll_options, F.text, ~F.text.in_(MENU_BUTTONS))
async def admin_poll_options(message: Message, state: FSMContext) -> None:
    options = parse_poll_options(message.text)
    if not POLL_OPTIONS_MIN <= len(options) <= POLL_OPTIONS_MAX:
        await message.answer(
            f"⚠️ Нужно от {POLL_OPTIONS_MIN} до {POLL_OPTIONS_MAX} вариантов, каждый с новой строки. "
            f"Сейчас: {len(options)}."
        )
        return
    if too_long := [o for o in options if len(o) > POLL_OPTION_MAX_LEN]:
        await message.answer(f"⚠️ Вариант слишком длинный (максимум {POLL_OPTION_MAX_LEN} символов):\n«{h(too_long[0])}»")
        return
    if len({o.casefold() for o in options}) != len(options):
        await message.answer("⚠️ Варианты не должны повторяться.")
        return

    question = (await state.get_data()).get("poll_question", "")
    await state.update_data(poll_options=options)
    await state.set_state(AdminStates.poll_confirm)
    preview = "\n".join(f"🔹 {h(o)}" for o in options)
    await message.answer(
        f"👀 <b>Предпросмотр голосования</b>\n\n<b>{h(question)}</b>\n\n{preview}\n\nСоздать?",
        reply_markup=poll_create_confirm_kb(),
    )


@router.callback_query(ConfirmCB.filter(F.scope == "poll"), AdminStates.poll_confirm)
async def admin_poll_confirm(
    cb: CallbackQuery, callback_data: ConfirmCB, state: FSMContext, db: Database, bot: Bot
) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return

    if callback_data.action == "cancel":
        await state.clear()
        await safe_edit(msg, "❌ Создание голосования отменено.")
        await msg.answer("Вы в главном меню.", reply_markup=main_menu(True))
        await cb.answer()
        return

    data = await state.get_data()
    question, options = data.get("poll_question"), data.get("poll_options")
    if not question or not options:
        await state.clear()
        await cb.answer("Данные голосования потеряны, начните заново.", show_alert=True)
        return

    poll_id = await db.create_poll(question, options, cb.from_user.id)
    await state.clear()
    await safe_edit(msg, f"✅ Голосование <b>№{poll_id}</b> создано:\n\n<b>{h(question)}</b>")
    await cb.answer("Голосование создано!")

    summary = "Голосование доступно в разделе «🗳️ Голосования»."
    if callback_data.action == "notify":
        await msg.answer("📢 Рассылаю приглашение всем пользователям…")
        sent, failed = await broadcast(
            bot,
            await db.get_all_user_ids(),
            f"🗳 <b>Новое школьное голосование!</b>\n\n{h(question)}\n\nТвой голос важен 💙",
            poll_invite_kb(poll_id),
        )
        summary += f"\nРассылка завершена: доставлено {sent}, не доставлено {failed}."
    await msg.answer(summary, reply_markup=main_menu(True))


# ── Управление голосованиями ─────────────────────────────────────────
@router.callback_query(AdmMenuCB.filter(F.section == "polls"))
@router.callback_query(AdmPollCB.filter(F.action == "list"))
async def admin_polls(cb: CallbackQuery, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    await safe_edit(msg, *(await build_admin_polls(db)))
    await cb.answer()


@router.callback_query(AdmPollCB.filter(F.action == "view"))
async def admin_poll_view(cb: CallbackQuery, callback_data: AdmPollCB, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    view = await render_admin_poll(db, callback_data.poll_id)
    if view is None:
        await cb.answer("Голосование не найдено.", show_alert=True)
        return
    await safe_edit(msg, *view)
    await cb.answer()


@router.callback_query(AdmPollCB.filter(F.action == "toggle"))
async def admin_poll_toggle(cb: CallbackQuery, callback_data: AdmPollCB, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    poll = await db.get_poll(callback_data.poll_id)
    if poll is None:
        await cb.answer("Голосование не найдено.", show_alert=True)
        return
    new_active = not poll["is_active"]
    await db.set_poll_active(poll["id"], new_active)
    view = await render_admin_poll(db, poll["id"])
    if view:
        await safe_edit(msg, *view)
    await cb.answer("Голосование возобновлено." if new_active else "Голосование завершено.")


@router.callback_query(AdmPollCB.filter(F.action == "del"))
async def admin_poll_delete_ask(cb: CallbackQuery, callback_data: AdmPollCB) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    await safe_edit(
        msg,
        f"🗑 Удалить голосование <b>№{callback_data.poll_id}</b> вместе со всеми голосами?\nЭто действие нельзя отменить.",
        admin_poll_delete_kb(callback_data.poll_id),
    )
    await cb.answer()


@router.callback_query(AdmPollCB.filter(F.action == "delok"))
async def admin_poll_delete(cb: CallbackQuery, callback_data: AdmPollCB, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    deleted = await db.delete_poll(callback_data.poll_id)
    await safe_edit(msg, *(await build_admin_polls(db)))
    await cb.answer("Голосование удалено." if deleted else "Голосование уже удалено.")


# ── Статистика ───────────────────────────────────────────────────────
@router.callback_query(AdmMenuCB.filter(F.section == "stats"))
async def admin_stats(cb: CallbackQuery, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    await safe_edit(msg, format_admin_stats(await db.get_stats()), back_to_admin_kb())
    await cb.answer()
