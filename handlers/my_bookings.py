import logging
from datetime import date

from aiogram import Bot, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import keyboards as kb
from config import config
from services import (
    get_user_bookings, get_booking, cancel_booking,
    CancelTooLate, MIN_CANCEL_HOURS,
)

router = Router()
log = logging.getLogger(__name__)


def fmt_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d.%m.%Y")


@router.callback_query(F.data == "menu:my")
async def show_my(call: CallbackQuery, state: FSMContext):
    await state.clear()
    bookings = await get_user_bookings(call.from_user.id)
    if not bookings:
        await call.message.edit_text(
            "У тебя пока нет активных записей.", reply_markup=kb.back_to_menu()
        )
    else:
        await call.message.edit_text(
            "📋 <b>Твои записи:</b>", reply_markup=kb.my_bookings_kb(bookings)
        )
    await call.answer()


@router.callback_query(F.data.startswith("mb:"))
async def show_card(call: CallbackQuery):
    b = await get_booking(int(call.data.split(":", 1)[1]), call.from_user.id)
    if not b:
        await call.answer("Запись не найдена или уже отменена", show_alert=True)
        return
    await call.message.edit_text(
        f"📋 <b>Запись №{b['id']}</b>\n\n"
        f"Услуга: {b['service_name']}\n"
        f"Дата: {fmt_date(b['date'])}\n"
        f"Время: {b['time']}\n"
        f"Цена: {b['price']} ₽",
        reply_markup=kb.booking_card_kb(b["id"]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("cx:"))
async def ask_cancel(call: CallbackQuery):
    b = await get_booking(int(call.data.split(":", 1)[1]), call.from_user.id)
    if not b:
        await call.answer("Запись не найдена или уже отменена", show_alert=True)
        return
    await call.message.edit_text(
        f"Отменить запись №{b['id']}?\n"
        f"{b['service_name']}, {fmt_date(b['date'])} в {b['time']}",
        reply_markup=kb.cancel_confirm_kb(b["id"]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("cxy:"))
async def do_cancel(call: CallbackQuery, bot: Bot):
    booking_id = int(call.data.split(":", 1)[1])
    try:
        b = await cancel_booking(booking_id, call.from_user.id)
    except CancelTooLate:
        await call.message.edit_text(
            f"Отменить онлайн можно не позднее чем за {MIN_CANCEL_HOURS} ч. до визита. "
            "Пожалуйста, свяжись с барбершопом по телефону.",
            reply_markup=kb.back_to_menu(),
        )
        await call.answer()
        return

    if not b:
        await call.answer("Запись уже отменена", show_alert=True)
        return

    await call.message.edit_text(
        f"✅ Запись №{b['id']} отменена.", reply_markup=kb.back_to_menu()
    )
    await call.answer()

    text = (
        f"❌ <b>Отмена записи №{b['id']}</b>\n"
        f"{b['service_name']}\n"
        f"{fmt_date(b['date'])} в {b['time']}\n"
        f"{b['client_name']}, {b['phone']}"
    )
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            log.exception("Не удалось уведомить админа %s", admin_id)

@router.callback_query(F.data.startswith("rem:ok:"))
async def reminder_ok(call: CallbackQuery):
    await call.message.edit_text(
        call.message.html_text + "\n\n✅ Отлично, ждём тебя!",
        reply_markup=None,
    )
    await call.answer()