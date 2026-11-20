import asyncio
import logging
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config import config
from db import init_db
from handlers import (
    menu, booking, my_bookings,
    admin, admin_services, admin_schedule,
    errors, fallback,
)
from reminders import reminder_loop


def setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        "bot.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console])


async def main() -> None:
    setup_logging()
    log = logging.getLogger("bot")

    await init_db()

    session = AiohttpSession(proxy=config.proxy_url) if config.proxy_url else None
    bot = Bot(
        token=config.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.include_router(errors.router)
    dp.include_router(menu.router)
    dp.include_router(booking.router)
    dp.include_router(my_bookings.router)
    dp.include_router(admin.router)
    dp.include_router(admin_services.router)
    dp.include_router(admin_schedule.router)
    dp.include_router(fallback.router)   # всегда последним

    reminders_task = asyncio.create_task(reminder_loop(bot))
    log.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        reminders_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())