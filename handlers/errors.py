import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent

router = Router()
log = logging.getLogger(__name__)


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    exc = event.exception

    # повторное нажатие на кнопку, текст не изменился: не ошибка
    if isinstance(exc, TelegramBadRequest) and "message is not modified" in str(exc):
        return True

    log.error("Необработанная ошибка: %r", exc, exc_info=exc)

    update = event.update
    try:
        if update.callback_query:
            await update.callback_query.answer(
                "Что-то пошло не так. Нажми /start и попробуй ещё раз.",
                show_alert=True,
            )
        elif update.message:
            await update.message.answer(
                "Что-то пошло не так. Нажми /start и попробуй ещё раз."
            )
    except Exception:
        pass  # например, callback устарел или клиент заблокировал бота
    return True