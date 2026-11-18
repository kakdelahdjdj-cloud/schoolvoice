"""
Настройки бота SchoolVoice.

Все секретные и изменяемые параметры читаются из переменных окружения
(или из файла .env рядом с этим файлом). Токен НИКОГДА не хранится в коде.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import timezone, tzinfo
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

# Корневая папка проекта
BASE_DIR = Path(__file__).resolve().parent

# Загружаем .env (если он есть). Уже заданные переменные окружения не перезаписываются.
load_dotenv(BASE_DIR / ".env")

# Формат токена Telegram: <число>:<строка из букв, цифр, _ и ->
_TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")


class ConfigError(Exception):
    """Ошибка конфигурации (например, не задан токен)."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Неизменяемый набор настроек приложения."""

    # repr=False — чтобы токен случайно не попал в логи при выводе объекта
    bot_token: str = field(repr=False)
    admin_ids: frozenset[int]
    db_path: Path
    timezone: tzinfo
    max_appeals_per_day: int
    show_author_to_admins: bool
    log_level: str


def _parse_admin_ids(raw: str) -> frozenset[int]:
    """Разбирает строку вида "123, 456" в множество ID администраторов."""
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.lstrip("-").isdigit():
            raise ConfigError(
                f"ADMIN_IDS содержит некорректное значение «{part}». "
                "Укажите числовые Telegram ID через запятую."
            )
        ids.add(int(part))
    return frozenset(ids)


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on", "да"}


def _parse_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} должно быть целым числом, получено «{raw}».") from exc
    if value < 0:
        raise ConfigError(f"{name} не может быть отрицательным.")
    return value


def _parse_timezone(raw: str) -> tzinfo:
    try:
        return ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError):
        # Если часовой пояс не найден — используем UTC, а не падаем
        return timezone.utc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает настройки (читаются один раз и кешируются)."""
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "Не задан BOT_TOKEN. Скопируйте .env.example в .env и впишите токен от @BotFather."
        )
    if not _TOKEN_RE.match(token):
        raise ConfigError(
            "BOT_TOKEN имеет неверный формат. Проверьте, что вы скопировали токен от @BotFather целиком."
        )

    db_raw = os.getenv("DB_PATH", "data/schoolvoice.db").strip() or "data/schoolvoice.db"
    db_path = Path(db_raw)
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path

    return Settings(
        bot_token=token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        db_path=db_path,
        timezone=_parse_timezone(os.getenv("TIMEZONE", "Asia/Tashkent").strip() or "UTC"),
        max_appeals_per_day=_parse_int("MAX_APPEALS_PER_DAY", 10),
        show_author_to_admins=_parse_bool(os.getenv("SHOW_AUTHOR_TO_ADMINS"), default=False),
        log_level=(os.getenv("LOG_LEVEL", "INFO").strip() or "INFO").upper(),
    )
