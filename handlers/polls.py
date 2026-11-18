"""🗳️ Голосования для пользователей: список, голосование, результаты."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from callbacks import PollCB, VoteCB
from constants import BTN_POLLS
from database import Database, VoteResult
from keyboards import poll_back_kb, poll_vote_kb, polls_list_kb
from utils import callback_message, format_poll_results, h, safe_edit

router = Router(name="polls")


async def build_polls_list(db: Database, closed: bool) -> tuple[str, InlineKeyboardMarkup]:
    polls = await db.list_polls(active=not closed, limit=30)
    if closed:
        title = "📁 <b>Завершённые голосования</b>"
        empty = "Завершённых голосований пока нет."
        hint = "Нажмите на опрос, чтобы посмотреть результаты."
    else:
        title = "🗳️ <b>Активные голосования</b>"
        empty = "Сейчас активных голосований нет. Загляните позже! 💙"
        hint = "Выберите опрос, чтобы проголосовать. Голосовать можно один раз в каждом опросе."
    text = f"{title}\n\n{hint if polls else empty}"
    return text, polls_list_kb(polls, closed)


async def build_poll_view(db: Database, poll_id: int, user_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    """Если пользователь ещё не голосовал в активном опросе — кнопки вариантов, иначе результаты."""
    poll = await db.get_poll(poll_id)
    if poll is None:
        return None
    user_option = await db.get_user_vote(poll_id, user_id)
    if poll["is_active"] and user_option is None:
        options = await db.get_poll_options(poll_id)
        text = f"🗳 <b>{h(poll['question'])}</b>\n\nВыберите один вариант ответа 👇\n<i>Изменить голос будет нельзя.</i>"
        return text, poll_vote_kb(poll_id, options)
    results = await db.get_poll_results(poll_id)
    return format_poll_results(poll, results, user_option), poll_back_kb(bool(poll["is_active"]))


@router.message(F.text == BTN_POLLS)
async def polls_menu(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    text, kb = await build_polls_list(db, closed=False)
    await message.answer(text, reply_markup=kb)


@router.callback_query(PollCB.filter(F.action.in_({"list", "closed"})))
async def polls_list(cb: CallbackQuery, callback_data: PollCB, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    text, kb = await build_polls_list(db, closed=callback_data.action == "closed")
    await safe_edit(msg, text, kb)
    await cb.answer()


@router.callback_query(PollCB.filter(F.action == "open"))
async def poll_open(cb: CallbackQuery, callback_data: PollCB, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    view = await build_poll_view(db, callback_data.poll_id, cb.from_user.id)
    if view is None:
        await cb.answer("Голосование не найдено — возможно, его удалили.", show_alert=True)
        return
    await safe_edit(msg, *view)
    await cb.answer()


@router.callback_query(VoteCB.filter())
async def poll_vote(cb: CallbackQuery, callback_data: VoteCB, db: Database) -> None:
    msg = await callback_message(cb)
    if msg is None:
        return
    result = await db.add_vote(callback_data.poll_id, cb.from_user.id, callback_data.option_id)
    notices = {
        VoteResult.OK: "✅ Ваш голос учтён!",
        VoteResult.ALREADY_VOTED: "Вы уже голосовали в этом опросе. Повторно голосовать нельзя.",
        VoteResult.POLL_CLOSED: "Голосование уже завершено.",
        VoteResult.NOT_FOUND: "Голосование или вариант не найдены.",
    }
    await cb.answer(notices[result], show_alert=result is not VoteResult.OK)

    view = await build_poll_view(db, callback_data.poll_id, cb.from_user.id)
    if view is not None:
        await safe_edit(msg, *view)
    else:
        text, kb = await build_polls_list(db, closed=False)
        await safe_edit(msg, text, kb)
