"""Общие команды: /start, /help, отмена, «О проекте»."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from constants import BOT_NAME, BTN_ABOUT, BTN_CANCEL, SLOGAN
from keyboards import main_menu
from utils import h, is_admin

router = Router(name="common")


def welcome_text(name: str) -> str:
    return (
        f"💙 Привет, <b>{h(name)}</b>!\n\n"
        f"Это <b>{BOT_NAME}</b> — «{SLOGAN}».\n\n"
        "Здесь ты можешь:\n"
        "📝 предложить идею для школы;\n"
        "⚠️ сообщить о проблеме;\n"
        "🗳️ участвовать в школьных голосованиях;\n"
        "📨 следить за статусом своих обращений.\n\n"
        "Выбери действие в меню ниже 👇"
    )


ABOUT_TEXT = (
    f"ℹ️ <b>О проекте {BOT_NAME}</b>\n"
    f"<i>«{SLOGAN}»</i>\n\n"
    "SchoolVoice — это канал связи между учениками и администрацией школы.\n\n"
    "🔹 <b>Предложения</b> — идеи, как сделать школу лучше.\n"
    "🔹 <b>Проблемы</b> — сообщения о неполадках: столовая, кабинеты, "
    "санитарное состояние, оборудование и другое.\n"
    "🔹 <b>Голосования</b> — мнение учеников по важным вопросам. "
    "В каждом опросе можно проголосовать только один раз.\n"
    "🔹 <b>Мои обращения</b> — статусы и ответы администрации:\n"
    "    🟡 На рассмотрении → 🔵 В обработке → 🟢 Решено\n\n"
    "🔒 <b>Конфиденциальность.</b> Твои обращения видишь только ты и администрация. "
    "Другие пользователи никогда не видят твоих данных, а статистика показывается только в общих цифрах.\n\n"
    "Команды: /start — меню, /cancel — отменить действие, /help — помощь."
)

HELP_TEXT = (
    "❓ <b>Как пользоваться ботом</b>\n\n"
    "1. Нажми кнопку в меню внизу экрана.\n"
    "2. Следуй подсказкам бота.\n"
    "3. Перед отправкой обращения ты увидишь предпросмотр и сможешь исправить текст.\n"
    "4. Чтобы прервать любое действие — нажми «❌ Отмена» или отправь /cancel.\n\n"
    "Если меню пропало — отправь /start."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    await message.answer(
        welcome_text(user.first_name if user else "друг"),
        reply_markup=main_menu(is_admin(user.id) if user else False),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu(is_admin(message.from_user.id)))


@router.message(Command("cancel"))
@router.message(F.text == BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Отмена любого диалога — работает из любого состояния."""
    had_state = await state.get_state() is not None
    await state.clear()
    text = "❌ Действие отменено." if had_state else "Сейчас нечего отменять."
    await message.answer(f"{text} Вы в главном меню.", reply_markup=main_menu(is_admin(message.from_user.id)))


@router.message(Command("about"))
@router.message(F.text == BTN_ABOUT)
async def about(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(ABOUT_TEXT, reply_markup=main_menu(is_admin(message.from_user.id)))


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery) -> None:
    """Кнопка-индикатор страницы — ничего не делает."""
    await cb.answer()
