"""
Подключение всех роутеров.

Порядок важен:
  1. common   — /start и «Отмена» должны срабатывать из любого состояния;
  2. admin    — перехватывает админские команды раньше fallback;
  3. разделы  — предложения, проблемы, голосования, обращения, статистика;
  4. fallback — всё необработанное (подключается последним).
"""

from aiogram import Router

from . import admin, appeals, common, fallback, polls, problems, stats, suggestions


def get_routers() -> list[Router]:
    return [
        common.router,
        admin.router,
        suggestions.router,
        problems.router,
        polls.router,
        appeals.router,
        stats.router,
        fallback.router,
    ]
