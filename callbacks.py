"""
Фабрики callback-данных для inline-кнопок.

Префиксы короткие, потому что Telegram ограничивает callback_data 64 байтами.
"""

from aiogram.filters.callback_data import CallbackData


class ConfirmCB(CallbackData, prefix="cf"):
    """Подтверждение действия. scope: sug | prb | poll; action: send | edit | cancel | notify | quiet."""

    scope: str
    action: str


class CategoryCB(CallbackData, prefix="cat"):
    """Выбор категории проблемы."""

    code: str


class PollCB(CallbackData, prefix="pl"):
    """Голосования для пользователя. action: list | closed | open."""

    action: str
    poll_id: int = 0


class VoteCB(CallbackData, prefix="vt"):
    """Голос за вариант ответа."""

    poll_id: int
    option_id: int


class MyAppealCB(CallbackData, prefix="ma"):
    """«Мои обращения». action: list | view."""

    action: str
    appeal_id: int = 0
    page: int = 0


class AdmMenuCB(CallbackData, prefix="am"):
    """Разделы админ-панели. section: home | all | sug | prb | newpoll | polls | stats."""

    section: str


class AdmListCB(CallbackData, prefix="al"):
    """Список обращений в админке. t: a | s | p; st: all | pending | progress | resolved."""

    t: str
    st: str
    page: int = 0


class AdmAppealCB(CallbackData, prefix="aa"):
    """Действия с обращением. action: view | st | reply | del | delok."""

    action: str
    appeal_id: int
    value: str = ""


class AdmPollCB(CallbackData, prefix="ap"):
    """Управление голосованиями. action: list | view | toggle | del | delok."""

    action: str
    poll_id: int = 0
