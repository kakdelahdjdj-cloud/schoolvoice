"""📊 Публичная статистика (только общие цифры, без личных данных)."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from constants import (
    BTN_STATS,
    CATEGORIES,
    STATUS_PENDING,
    STATUS_PROGRESS,
    STATUS_RESOLVED,
    TYPE_PROBLEM,
    TYPE_SUGGESTION,
)
from database import Database
from keyboards import main_menu
from utils import is_admin, progress_bar

router = Router(name="stats")


def format_public_stats(s: dict) -> str:
    total = s["appeals_total"]
    resolved = s["by_status"].get(STATUS_RESOLVED, 0)
    resolved_pct = resolved / total * 100 if total else 0
    lines = [
        "📊 <b>Статистика SchoolVoice</b>",
        "",
        f"👥 Участников: <b>{s['users']}</b>",
        f"📬 Всего обращений: <b>{total}</b>",
        f"   💡 Предложений: {s['by_type'].get(TYPE_SUGGESTION, 0)}",
        f"   ⚠️ Проблем: {s['by_type'].get(TYPE_PROBLEM, 0)}",
        "",
        "<b>Статусы:</b>",
        f"🟡 На рассмотрении: {s['by_status'].get(STATUS_PENDING, 0)}",
        f"🔵 В обработке: {s['by_status'].get(STATUS_PROGRESS, 0)}",
        f"🟢 Решено: {resolved}",
        f"{progress_bar(resolved_pct)} {resolved_pct:.0f}% решено",
    ]
    if s["by_category"]:
        lines += ["", "<b>Проблемы по категориям:</b>"]
        for code, title in CATEGORIES.items():
            if count := s["by_category"].get(code, 0):
                lines.append(f"{title}: {count}")
    lines += [
        "",
        f"🗳️ Голосований: {s['polls_total']} (активных: {s['polls_active']})",
        f"✋ Отдано голосов: {s['votes_total']}",
        "",
        "💙 Каждый голос меняет школу!",
    ]
    return "\n".join(lines)


@router.message(F.text == BTN_STATS)
async def public_stats(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    stats = await db.get_stats()
    await message.answer(format_public_stats(stats), reply_markup=main_menu(is_admin(message.from_user.id)))
