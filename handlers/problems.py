"""⚠️ Сообщение о проблеме: категория → описание → предпросмотр → подтверждение."""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from callbacks import CategoryCB, ConfirmCB
from constants import (
    BTN_PROBLEM,
    CATEGORIES,
    MENU_BUTTONS,
    TEXT_MAX_LEN,
    TEXT_MIN_LEN,
    TYPE_PROBLEM,
)
from database import Database
from keyboards import cancel_kb, categories_kb, confirm_kb, main_menu
from states import ProblemStates
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

router = Router(name="problems")


@router.message(F.text == BTN_PROBLEM)
async def start_problem(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    if await appeal_limit_reached(db, message.from_user.id):
        await message.answer(limit_message(), reply_markup=main_menu(is_admin(message.from_user.id)))
        return
    await state.set_state(ProblemStates.category)
    # Первое сообщение ставит клавиатуру «Отмена», второе — выбор категории
    await message.answer("⚠️ <b>Сообщить о проблеме</b>", reply_markup=cancel_kb())
    await message.answer("Выберите категорию проблемы:", reply_markup=categories_kb())


@router.callback_query(CategoryCB.filter(), ProblemStates.category)
async def problem_category(cb: CallbackQuery, callback_data: CategoryCB, state: FSMContext) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    if callback_data.code not in CATEGORIES:
        await cb.answer("Неизвестная категория.", show_alert=True)
        return
    await state.update_data(category=callback_data.code)
    await state.set_state(ProblemStates.text)
    await safe_edit(
        msg,
        f"Категория: <b>{CATEGORIES[callback_data.code]}</b>\n\n"
        "Опишите проблему одним сообщением: <b>что</b> случилось и <b>где</b> "
        "(например, номер кабинета).\n"
        f"<i>От {TEXT_MIN_LEN} до {TEXT_MAX_LEN} символов.</i>",
    )
    await cb.answer()


@router.message(ProblemStates.text, F.text, ~F.text.in_(MENU_BUTTONS))
async def problem_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if error := validate_length(text, TEXT_MIN_LEN, TEXT_MAX_LEN):
        await message.answer(f"⚠️ {error} Попробуйте ещё раз.")
        return
    data = await state.get_data()
    await state.update_data(text=text)
    await state.set_state(ProblemStates.confirm)
    await message.answer(
        "👀 <b>Проверьте сообщение о проблеме:</b>\n\n"
        f"Категория: {CATEGORIES.get(data.get('category', 'other'), '📌 Другое')}\n\n"
        f"{h(text)}\n\nВсё верно?",
        reply_markup=confirm_kb("prb"),
    )


@router.callback_query(ConfirmCB.filter(F.scope == "prb"), ProblemStates.confirm)
async def problem_confirm(
    cb: CallbackQuery, callback_data: ConfirmCB, state: FSMContext, db: Database, bot: Bot
) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    uid = cb.from_user.id

    if callback_data.action == "edit":
        await state.set_state(ProblemStates.text)
        await safe_edit(msg, "✏️ Отправьте исправленное описание проблемы.")
        await cb.answer()
        return

    if callback_data.action == "cancel":
        await state.clear()
        await safe_edit(msg, "❌ Сообщение о проблеме отменено.")
        await msg.answer("Вы в главном меню.", reply_markup=main_menu(is_admin(uid)))
        await cb.answer()
        return

    data = await state.get_data()
    text, category = data.get("text"), data.get("category")
    if not text or category not in CATEGORIES:
        await state.clear()
        await cb.answer("Данные не найдены, начните заново.", show_alert=True)
        return
    if await appeal_limit_reached(db, uid):
        await state.clear()
        await safe_edit(msg, limit_message())
        await cb.answer()
        return

    appeal_id = await submit_appeal(db, bot, uid, TYPE_PROBLEM, text, category)
    await state.clear()
    await safe_edit(msg, f"⚠️ <b>Обращение №{appeal_id}</b> · {CATEGORIES[category]}\n\n{h(text)}")
    await msg.answer(
        f"✅ <b>Спасибо! Сообщение о проблеме №{appeal_id} принято.</b>\n\n"
        "Статус: 🟡 На рассмотрении.\n"
        "Следить за ним можно в разделе «📨 Мои обращения».",
        reply_markup=main_menu(is_admin(uid)),
    )
    await cb.answer("Отправлено!")
