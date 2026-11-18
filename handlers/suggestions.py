"""📝 Отправка предложений: текст → предпросмотр → подтверждение."""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from callbacks import ConfirmCB
from constants import BTN_SUGGEST, MENU_BUTTONS, TEXT_MAX_LEN, TEXT_MIN_LEN, TYPE_SUGGESTION
from database import Database
from keyboards import cancel_kb, confirm_kb, main_menu
from states import SuggestionStates
from utils import (
    appeal_limit_reached,
    callback_message,
    h,
    is_admin,
    limit_message,
    safe_edit,
    submit_appeal,
    validate_length,
)

router = Router(name="suggestions")

PROMPT = (
    "📝 <b>Новое предложение</b>\n\n"
    "Опишите вашу идею одним сообщением: что предлагаете и чем это поможет школе.\n"
    f"<i>От {TEXT_MIN_LEN} до {TEXT_MAX_LEN} символов.</i>\n\n"
    "Чтобы выйти — нажмите «❌ Отмена»."
)


@router.message(F.text == BTN_SUGGEST)
async def start_suggestion(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    if await appeal_limit_reached(db, message.from_user.id):
        await message.answer(limit_message(), reply_markup=main_menu(is_admin(message.from_user.id)))
        return
    await state.set_state(SuggestionStates.text)
    await message.answer(PROMPT, reply_markup=cancel_kb())


@router.message(SuggestionStates.text, F.text, ~F.text.in_(MENU_BUTTONS))
async def suggestion_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if error := validate_length(text, TEXT_MIN_LEN, TEXT_MAX_LEN):
        await message.answer(f"⚠️ {error} Попробуйте ещё раз.")
        return
    await state.update_data(text=text)
    await state.set_state(SuggestionStates.confirm)
    await message.answer(
        f"👀 <b>Проверьте предложение:</b>\n\n{h(text)}\n\nВсё верно?",
        reply_markup=confirm_kb("sug"),
    )


@router.callback_query(ConfirmCB.filter(F.scope == "sug"), SuggestionStates.confirm)
async def suggestion_confirm(
    cb: CallbackQuery, callback_data: ConfirmCB, state: FSMContext, db: Database, bot: Bot
) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    uid = cb.from_user.id

    if callback_data.action == "edit":
        await state.set_state(SuggestionStates.text)
        await safe_edit(msg, "✏️ Отправьте исправленный текст предложения.")
        await cb.answer()
        return

    if callback_data.action == "cancel":
        await state.clear()
        await safe_edit(msg, "❌ Отправка предложения отменена.")
        await msg.answer("Вы в главном меню.", reply_markup=main_menu(is_admin(uid)))
        await cb.answer()
        return

    # action == "send"
    text = (await state.get_data()).get("text")
    if not text:
        await state.clear()
        await cb.answer("Текст не найден, начните заново.", show_alert=True)
        return
    if await appeal_limit_reached(db, uid):
        await state.clear()
        await safe_edit(msg, limit_message())
        await cb.answer()
        return

    appeal_id = await submit_appeal(db, bot, uid, TYPE_SUGGESTION, text)
    await state.clear()
    await safe_edit(msg, f"📝 <b>Предложение №{appeal_id}</b>\n\n{h(text)}")
    await msg.answer(
        f"✅ <b>Спасибо! Предложение №{appeal_id} отправлено.</b>\n\n"
        "Статус: 🟡 На рассмотрении.\n"
        "Следить за ним можно в разделе «📨 Мои обращения» — там же появится ответ администрации.",
        reply_markup=main_menu(is_admin(uid)),
    )
    await cb.answer("Отправлено!")
