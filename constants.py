"""Константы проекта: тексты кнопок, статусы, категории и лимиты."""

BOT_NAME = "SchoolVoice"
SLOGAN = "Твой голос меняет школу"

# ── Кнопки главного меню ─────────────────────────────────────────────
BTN_SUGGEST = "📝 Отправить предложение"
BTN_PROBLEM = "⚠️ Сообщить о проблеме"
BTN_POLLS = "🗳️ Голосования"
BTN_MY = "📨 Мои обращения"
BTN_STATS = "📊 Статистика"
BTN_ABOUT = "ℹ️ О проекте"
BTN_ADMIN = "🛠 Админ-панель"
BTN_CANCEL = "❌ Отмена"

# Тексты, которые не должны восприниматься как ввод пользователя в диалогах
MENU_BUTTONS = frozenset(
    {BTN_SUGGEST, BTN_PROBLEM, BTN_POLLS, BTN_MY, BTN_STATS, BTN_ABOUT, BTN_ADMIN, BTN_CANCEL}
)

# ── Типы обращений ───────────────────────────────────────────────────
TYPE_SUGGESTION = "suggestion"
TYPE_PROBLEM = "problem"

APPEAL_TYPES = {
    TYPE_SUGGESTION: "💡 Предложение",
    TYPE_PROBLEM: "⚠️ Проблема",
}

# Короткие коды для callback-данных (лимит Telegram — 64 байта)
TYPE_CODES = {"s": TYPE_SUGGESTION, "p": TYPE_PROBLEM}

# ── Статусы обращений ────────────────────────────────────────────────
STATUS_PENDING = "pending"
STATUS_PROGRESS = "progress"
STATUS_RESOLVED = "resolved"

STATUSES = {
    STATUS_PENDING: "🟡 На рассмотрении",
    STATUS_PROGRESS: "🔵 В обработке",
    STATUS_RESOLVED: "🟢 Решено",
}

STATUS_EMOJI = {
    STATUS_PENDING: "🟡",
    STATUS_PROGRESS: "🔵",
    STATUS_RESOLVED: "🟢",
}

# ── Категории проблем ────────────────────────────────────────────────
CATEGORIES = {
    "canteen": "🍽 Столовая",
    "rooms": "🚪 Кабинеты",
    "sanitary": "🧼 Санитарное состояние",
    "equipment": "🖥 Оборудование",
    "other": "📌 Другое",
}

# ── Лимиты ───────────────────────────────────────────────────────────
TEXT_MIN_LEN = 10
TEXT_MAX_LEN = 2000
REPLY_MIN_LEN = 2
REPLY_MAX_LEN = 2000

POLL_QUESTION_MIN = 5
POLL_QUESTION_MAX = 300
POLL_OPTIONS_MIN = 2
POLL_OPTIONS_MAX = 10
POLL_OPTION_MAX_LEN = 80

USER_PAGE_SIZE = 5
ADMIN_PAGE_SIZE = 8
ADMIN_POLLS_LIMIT = 30
