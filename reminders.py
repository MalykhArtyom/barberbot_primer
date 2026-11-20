import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

import keyboards as kb
from services import (
    now_local, get_pending_reminders, claim_reminder, MIN_CANCEL_HOURS,
)

log = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 60


async def _send(bot: Bot, user_id: int, text: str, markup) -> None:
    try:
        await bot.send_message(user_id, text, reply_markup=markup)
    except TelegramForbiddenError:
        log.info("Клиент %s заблокировал бота, напоминание пропущено", user_id)
    except Exception:
        log.exception("Не удалось отправить напоминание клиенту %s", user_id)


async def process_reminders(bot: Bot) -> None:
    now = now_local()
    for b in await get_pending_reminders():
        start = datetime.fromisoformat(f"{b['date']} {b['time']}")
        until = start - now

        # визит уже начался или прошёл: гасим всё молча
        if until <= timedelta(0):
            await claim_reminder(b["id"], "24h")
            await claim_reminder(b["id"], "2h")
            continue

        if not b["reminded_24h"] and until <= timedelta(hours=24):
            if await claim_reminder(b["id"], "24h") and until > timedelta(hours=2):
                await _send(
                    bot, b["user_id"],
                    "⏰ <b>Напоминание о записи</b>\n\n"
                    f"Завтра ждём тебя: {b['service_name']}, {b['time']}.\n"
                    "Если планы изменились, отмени запись заранее, "
                    "чтобы время мог занять другой клиент.",
                    kb.reminder_kb(b["id"], allow_cancel=True),
                )
                await asyncio.sleep(0.05)

        if not b["reminded_2h"] and until <= timedelta(hours=2):
            if await claim_reminder(b["id"], "2h"):
                await _send(
                    bot, b["user_id"],
                    "⏰ <b>Скоро визит!</b>\n\n"
                    f"Через пару часов: {b['service_name']}, {b['time']}.\n"
                    f"Если не получается прийти, позвони нам: онлайн-отмена "
                    f"доступна не позднее чем за {MIN_CANCEL_HOURS} ч.",
                    kb.reminder_kb(b["id"], allow_cancel=False),
                )
                await asyncio.sleep(0.05)


async def reminder_loop(bot: Bot) -> None:
    log.info("Планировщик напоминаний запущен")
    while True:
        try:
            await process_reminders(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(CHECK_INTERVAL_SEC)