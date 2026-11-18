"""Все клавиатуры бота (reply- и inline-кнопки)."""

from __future__ import annotations

from typing import Any

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from callbacks import (
    AdmAppealCB,
    AdmListCB,
    AdmMenuCB,
    AdmPollCB,
    CategoryCB,
    ConfirmCB,
    MyAppealCB,
    PollCB,
    VoteCB,
)
from constants import (
    BTN_ABOUT,
    BTN_ADMIN,
    BTN_CANCEL,
    BTN_MY,
    BTN_POLLS,
    BTN_PROBLEM,
    BTN_STATS,
    BTN_SUGGEST,
    CATEGORIES,
    STATUS_EMOJI,
    STATUSES,
)


def _btn(text: str, cb: CallbackData) -> InlineKeyboardButton:
    """Короткий помощник для создания inline-кнопки."""
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


def _chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _short(text: str, limit: int = 40) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _nav_row(make_cb, page: int, pages: int) -> list[InlineKeyboardButton]:
    """Строка пагинации: ◀️ 1/3 ▶️."""
    if pages <= 1:
        return []
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(_btn("◀️", make_cb(page - 1)))
    row.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        row.append(_btn("▶️", make_cb(page + 1)))
    return row


# ── Reply-клавиатуры ─────────────────────────────────────────────────
def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_SUGGEST), KeyboardButton(text=BTN_PROBLEM)],
        [KeyboardButton(text=BTN_POLLS), KeyboardButton(text=BTN_MY)],
        [KeyboardButton(text=BTN_STATS), KeyboardButton(text=BTN_ABOUT)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(
        keyboard=rows, resize_keyboard=True, input_field_placeholder="Выберите действие…"
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder="Введите текст…",
    )


# ── Отправка обращений ───────────────────────────────────────────────
def confirm_kb(scope: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("✅ Отправить", ConfirmCB(scope=scope, action="send"))],
            [
                _btn("✏️ Изменить текст", ConfirmCB(scope=scope, action="edit")),
                _btn("❌ Отменить", ConfirmCB(scope=scope, action="cancel")),
            ],
        ]
    )


def categories_kb() -> InlineKeyboardMarkup:
    buttons = [_btn(title, CategoryCB(code=code)) for code, title in CATEGORIES.items()]
    return InlineKeyboardMarkup(inline_keyboard=_chunks(buttons, 2))


# ── Голосования (пользователь) ───────────────────────────────────────
def polls_list_kb(polls: list[dict], closed: bool) -> InlineKeyboardMarkup:
    icon = "📁" if closed else "🗳"
    rows = [[_btn(f"{icon} {_short(p['question'])}", PollCB(action="open", poll_id=p["id"]))] for p in polls]
    if closed:
        rows.append([_btn("🗳 Активные голосования", PollCB(action="list"))])
    else:
        rows.append([_btn("📁 Завершённые голосования", PollCB(action="closed"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def poll_vote_kb(poll_id: int, options: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"🔹 {_short(o['text'], 60)}", VoteCB(poll_id=poll_id, option_id=o["id"]))]
        for o in options
    ]
    rows.append([_btn("⬅️ К списку", PollCB(action="list"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def poll_back_kb(is_active: bool) -> InlineKeyboardMarkup:
    action = "list" if is_active else "closed"
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ К списку", PollCB(action=action))]])


def poll_invite_kb(poll_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn("🗳 Проголосовать", PollCB(action="open", poll_id=poll_id))]]
    )


# ── Мои обращения ────────────────────────────────────────────────────
def my_appeals_kb(appeals: list[dict], page: int, pages: int) -> InlineKeyboardMarkup:
    buttons = [
        _btn(
            f"{STATUS_EMOJI.get(a['status'], '•')} №{a['id']}",
            MyAppealCB(action="view", appeal_id=a["id"], page=page),
        )
        for a in appeals
    ]
    rows = _chunks(buttons, 3)
    nav = _nav_row(lambda p: MyAppealCB(action="list", page=p), page, pages)
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_appeal_back_kb(page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn("⬅️ К моим обращениям", MyAppealCB(action="list", page=page))]]
    )


def user_appeal_open_kb(appeal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn("📨 Открыть обращение", MyAppealCB(action="view", appeal_id=appeal_id))]]
    )


# ── Админ-панель ─────────────────────────────────────────────────────
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("📥 Все обращения", AdmMenuCB(section="all"))],
            [
                _btn("💡 Предложения", AdmMenuCB(section="sug")),
                _btn("⚠️ Проблемы", AdmMenuCB(section="prb")),
            ],
            [
                _btn("➕ Создать голосование", AdmMenuCB(section="newpoll")),
                _btn("🗂 Голосования", AdmMenuCB(section="polls")),
            ],
            [_btn("📊 Статистика", AdmMenuCB(section="stats"))],
        ]
    )


def back_to_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ Админ-панель", AdmMenuCB(section="home"))]])


def admin_list_kb(appeals: list[dict], t: str, st: str, page: int, pages: int) -> InlineKeyboardMarkup:
    # Фильтр по статусу (текущий отмечен галочкой)
    filters = [("all", "Все")] + [(code, STATUS_EMOJI[code]) for code in STATUSES]
    filter_row = [
        _btn(("✓ " if code == st else "") + label, AdmListCB(t=t, st=code, page=0))
        for code, label in filters
    ]
    rows: list[list[InlineKeyboardButton]] = [filter_row]

    buttons = [
        _btn(f"{STATUS_EMOJI.get(a['status'], '•')} №{a['id']}", AdmAppealCB(action="view", appeal_id=a["id"]))
        for a in appeals
    ]
    rows.extend(_chunks(buttons, 4))

    nav = _nav_row(lambda p: AdmListCB(t=t, st=st, page=p), page, pages)
    if nav:
        rows.append(nav)
    rows.append([_btn("⬅️ Админ-панель", AdmMenuCB(section="home"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_appeal_kb(appeal: dict, back: dict) -> InlineKeyboardMarkup:
    appeal_id = appeal["id"]
    status_buttons = [
        _btn(label, AdmAppealCB(action="st", appeal_id=appeal_id, value=code))
        for code, label in STATUSES.items()
        if code != appeal["status"]
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("✍️ Ответить", AdmAppealCB(action="reply", appeal_id=appeal_id))],
            status_buttons,
            [_btn("🗑 Удалить", AdmAppealCB(action="del", appeal_id=appeal_id))],
            [_btn("⬅️ К списку", AdmListCB(t=back["t"], st=back["st"], page=back["page"]))],
        ]
    )


def admin_delete_confirm_kb(appeal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("🗑 Да, удалить", AdmAppealCB(action="delok", appeal_id=appeal_id)),
                _btn("↩️ Нет", AdmAppealCB(action="view", appeal_id=appeal_id)),
            ]
        ]
    )


def admin_notify_kb(appeal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn("🔎 Открыть обращение", AdmAppealCB(action="view", appeal_id=appeal_id))]]
    )


def poll_create_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("✅ Создать и разослать всем", ConfirmCB(scope="poll", action="notify"))],
            [_btn("✅ Создать без рассылки", ConfirmCB(scope="poll", action="quiet"))],
            [_btn("❌ Отменить", ConfirmCB(scope="poll", action="cancel"))],
        ]
    )


def admin_polls_kb(polls: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(
                f"{'🟢' if p['is_active'] else '⏹'} {_short(p['question'], 35)} · {p['votes']}",
                AdmPollCB(action="view", poll_id=p["id"]),
            )
        ]
        for p in polls
    ]
    rows.append([_btn("➕ Создать голосование", AdmMenuCB(section="newpoll"))])
    rows.append([_btn("⬅️ Админ-панель", AdmMenuCB(section="home"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_poll_kb(poll: dict) -> InlineKeyboardMarkup:
    toggle = "⏹ Завершить голосование" if poll["is_active"] else "▶️ Возобновить голосование"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(toggle, AdmPollCB(action="toggle", poll_id=poll["id"]))],
            [_btn("🗑 Удалить", AdmPollCB(action="del", poll_id=poll["id"]))],
            [_btn("⬅️ К голосованиям", AdmPollCB(action="list"))],
        ]
    )


def admin_poll_delete_kb(poll_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("🗑 Да, удалить", AdmPollCB(action="delok", poll_id=poll_id)),
                _btn("↩️ Нет", AdmPollCB(action="view", poll_id=poll_id)),
            ]
        ]
    )
