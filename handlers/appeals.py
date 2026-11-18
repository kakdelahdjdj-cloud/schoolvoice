"""📨 «Мои обращения»: пользователь видит только свои обращения и ответы на них."""

import math

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from callbacks import MyAppealCB
from constants import APPEAL_TYPES, BTN_MY, STATUS_EMOJI, USER_PAGE_SIZE
from database import Database
from keyboards import my_appeal_back_kb, my_appeals_kb
from utils import callback_message, fmt_dt, format_appeal_card, h, one_line, safe_edit

router = Router(name="appeals")


async def build_my_list(db: Database, user_id: int, page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    total = await db.count_user_appeals(user_id)
    if total == 0:
        return (
            "📨 <b>Мои обращения</b>\n\nУ вас пока нет обращений.\n"
            "Отправьте предложение или сообщите о проблеме через меню 👇",
            None,
        )
    pages = math.ceil(total / USER_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    appeals = await db.list_user_appeals(user_id, USER_PAGE_SIZE, page * USER_PAGE_SIZE)

    lines = [f"📨 <b>Мои обращения</b> (всего: {total})", ""]
    for a in appeals:
        lines.append(
            f"{STATUS_EMOJI.get(a['status'], '•')} <b>№{a['id']}</b> · "
            f"{APPEAL_TYPES.get(a['type'], '')} · {fmt_dt(a['created_at'])}\n"
            f"<i>{h(one_line(a['text'], 70))}</i>"
        )
    lines += ["", "🟡 На рассмотрении · 🔵 В обработке · 🟢 Решено", "Нажмите на номер, чтобы открыть обращение."]
    return "\n".join(lines), my_appeals_kb(appeals, page, pages)


@router.message(F.text == BTN_MY)
async def my_appeals(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    text, kb = await build_my_list(db, message.from_user.id, 0)
    await message.answer(text, reply_markup=kb)


@router.callback_query(MyAppealCB.filter(F.action == "list"))
async def my_appeals_page(cb: CallbackQuery, callback_data: MyAppealCB, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    text, kb = await build_my_list(db, cb.from_user.id, callback_data.page)
    await safe_edit(msg, text, kb)
    await cb.answer()


@router.callback_query(MyAppealCB.filter(F.action == "view"))
async def my_appeal_view(cb: CallbackQuery, callback_data: MyAppealCB, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    appeal = await db.get_appeal(callback_data.appeal_id)
    # Защита: чужое обращение показываем как «не найдено»
    if appeal is None or appeal["user_id"] != cb.from_user.id:
        await cb.answer("Обращение не найдено.", show_alert=True)
        return
    responses = await db.get_responses(appeal["id"])
    await safe_edit(msg, format_appeal_card(appeal, responses), my_appeal_back_kb(callback_data.page))
    await cb.answer()
