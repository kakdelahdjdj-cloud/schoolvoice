"""Состояния конечного автомата (FSM) для пошаговых диалогов."""

from aiogram.fsm.state import State, StatesGroup


class SuggestionStates(StatesGroup):
    text = State()      # ждём текст предложения
    confirm = State()   # ждём подтверждения отправки


class ProblemStates(StatesGroup):
    category = State()  # ждём выбора категории
    text = State()      # ждём описание проблемы
    confirm = State()   # ждём подтверждения


class AdminStates(StatesGroup):
    reply_text = State()      # ответ на обращение
    poll_question = State()   # вопрос нового голосования
    poll_options = State()    # варианты ответов
    poll_confirm = State()    # подтверждение создания
