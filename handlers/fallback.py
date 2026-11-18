"""
Обработчики «на всякий случай». Этот роутер подключается ПОСЛЕДНИМ:
сюда попадает всё, что не обработали остальные.
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from constants import BTN_ADMIN
from keyboards import main_menu
from utils import is_admin

router = Router(name="fallback")


@router.message(Command("admin"))
@router.message(F.text == BTN_ADMIN)
async def admin_denied(message: Message) -> None:
    """Сюда попадают только не-администраторы (админов перехватывает admin-роутер)."""
    await message.answer(
        "⛔ Панель администрации доступна только администраторам школы.",
        reply_markup=main_menu(False),
    )


@router.message()
async def unknown_message(message: Message, state: FSMContext) -> None:
    if await state.get_state() is not None:
        await message.answer(
            "Пожалуйста, следуйте подсказке выше: отправьте ответ текстом или нажмите кнопку под сообщением.\n"
            "Чтобы выйти — нажмите «❌ Отмена» или отправьте /cancel."
        )
        return
    await message.answer(
        "Я не понял сообщение 🤔 Выберите действие в меню ниже.",
        reply_markup=main_menu(is_admin(message.from_user.id)),
    )


@router.callback_query()
async def stale_callback(cb: CallbackQuery) -> None:
    await cb.answer("Эта кнопка устарела. Откройте раздел заново из меню.", show_alert=True)
