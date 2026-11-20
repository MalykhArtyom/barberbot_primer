from aiogram import Router
from aiogram.types import CallbackQuery, Message

import keyboards as kb

router = Router()


@router.message()
async def unknown_message(message: Message):
    await message.answer(
        "Не понял сообщение 🤔 Выбери действие в меню:",
        reply_markup=kb.main_menu(),
    )


@router.callback_query()
async def stale_button(call: CallbackQuery):
    await call.answer("Эта кнопка устарела. Открой меню: /start", show_alert=True)