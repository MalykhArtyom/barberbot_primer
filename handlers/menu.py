from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import keyboards as kb
import texts
from services import get_active_services

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        texts.WELCOME.format(name=message.from_user.first_name),
        reply_markup=kb.main_menu(),
    )


@router.callback_query(F.data == "menu:main")
async def to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        texts.WELCOME.format(name=call.from_user.first_name),
        reply_markup=kb.main_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "menu:contacts")
async def show_contacts(call: CallbackQuery):
    await call.message.edit_text(texts.CONTACTS, reply_markup=kb.back_to_menu())
    await call.answer()


@router.callback_query(F.data == "menu:services")
async def show_services(call: CallbackQuery):
    services = await get_active_services()
    lines = [
        f"• {s['name']}: {s['price']} ₽, {s['duration_min']} мин"
        for s in services
    ]
    await call.message.edit_text(
        texts.SERVICES_HEADER + "\n".join(lines),
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()