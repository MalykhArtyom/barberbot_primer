import logging
import re
from datetime import date

from aiogram import Bot, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import keyboards as kb
from config import config
from services import (
    get_active_services, get_service,
    get_available_dates, get_free_slots,
    create_booking, SlotTaken, LimitReached,
)

router = Router()
log = logging.getLogger(__name__)


class Booking(StatesGroup):
    service = State()
    date = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()

# ---------- шаг 1: услуга ----------
async def show_services(call: CallbackQuery, state: FSMContext):
    services = await get_active_services()
    await state.set_state(Booking.service)
    await call.message.edit_text(
        "✂️ <b>Выбери услугу:</b>", reply_markup=kb.services_kb(services)
    )


@router.callback_query(F.data == "menu:book")
async def start_booking(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_services(call, state)
    await call.answer()


@router.callback_query(F.data == "back:services")
async def back_to_services(call: CallbackQuery, state: FSMContext):
    await show_services(call, state)
    await call.answer()


# ---------- шаг 2: дата ----------
async def show_dates(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    dates = await get_available_dates(data["service_id"])
    if not dates:
        await call.answer("Нет доступных дат", show_alert=True)
        return
    await state.set_state(Booking.date)
    await call.message.edit_text(
        "📅 <b>Выбери дату:</b>", reply_markup=kb.dates_kb(dates)
    )


@router.callback_query(Booking.service, F.data.startswith("svc:"))
async def choose_service(call: CallbackQuery, state: FSMContext):
    service = await get_service(int(call.data.split(":", 1)[1]))
    if not service:
        await call.answer("Услуга недоступна", show_alert=True)
        return
    await state.update_data(service_id=service["id"], service_name=service["name"])
    await show_dates(call, state)
    await call.answer()


@router.callback_query(F.data == "back:dates")
async def back_to_dates(call: CallbackQuery, state: FSMContext):
    await show_dates(call, state)
    await call.answer()


# ---------- шаг 3: время ----------
@router.callback_query(Booking.date, F.data.startswith("date:"))
async def choose_date(call: CallbackQuery, state: FSMContext):
    day = date.fromisoformat(call.data.split(":", 1)[1])
    data = await state.get_data()
    slots = await get_free_slots(day, data["service_id"])
    if not slots:
        await call.answer("На этот день свободного времени нет", show_alert=True)
        return
    await state.update_data(date=day.isoformat())
    await state.set_state(Booking.time)
    await call.message.edit_text(
        f"🕒 <b>Выбери время на {day.strftime('%d.%m')}:</b>",
        reply_markup=kb.times_kb(slots),
    )
    await call.answer()


@router.callback_query(Booking.time, F.data.startswith("time:"))
async def choose_time(call: CallbackQuery, state: FSMContext):
    await state.update_data(time=call.data.split(":", 1)[1])
    await state.set_state(Booking.name)
    await call.message.edit_text(
        "👤 <b>Как тебя зовут?</b>", reply_markup=kb.cancel_kb()
    )
    await call.answer()

# ---------- имя ----------
@router.message(Booking.name, F.text)
async def enter_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not 2 <= len(name) <= 40:
        await message.answer("Имя должно быть от 2 до 40 символов. Попробуй ещё раз.")
        return
    await state.update_data(client_name=name)
    await state.set_state(Booking.phone)
    await message.answer(
        "📱 <b>Номер телефона для связи:</b>\n"
        "Нажми кнопку ниже или введи номер вручную.",
        reply_markup=kb.phone_kb(),
    )


# ---------- телефон ----------
def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if not 10 <= len(digits) <= 15:
        return None
    return "+" + digits


async def show_summary(message: Message, state: FSMContext, phone: str):
    await state.update_data(phone=phone)
    data = await state.get_data()
    day = date.fromisoformat(data["date"])
    await state.set_state(Booking.confirm)
    await message.answer("Почти готово 👇", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "📝 <b>Проверь запись:</b>\n\n"
        f"Услуга: {data['service_name']}\n"
        f"Дата: {day.strftime('%d.%m.%Y')}\n"
        f"Время: {data['time']}\n"
        f"Имя: {data['client_name']}\n"
        f"Телефон: {phone}",
        reply_markup=kb.confirm_kb(),
    )


@router.message(Booking.phone, F.contact)
async def phone_from_contact(message: Message, state: FSMContext):
    phone = normalize_phone(message.contact.phone_number)
    if not phone:
        await message.answer("Не удалось распознать номер, введи его вручную.")
        return
    await show_summary(message, state, phone)


@router.message(Booking.phone, F.text)
async def phone_from_text(message: Message, state: FSMContext):
    phone = normalize_phone(message.text)
    if not phone:
        await message.answer(
            "Номер выглядит неверно. Пример: +7 900 123-45-67. Попробуй ещё раз."
        )
        return
    await show_summary(message, state, phone)


# ---------- подтверждение ----------
@router.callback_query(Booking.confirm, F.data == "confirm:yes")
async def confirm(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    day = date.fromisoformat(data["date"])

    try:
        booking_id = await create_booking(
            user_id=call.from_user.id,
            service_id=data["service_id"],
            day=day,
            time_=data["time"],
            name=data["client_name"],
            phone=data["phone"],
        )
    except SlotTaken:
        await state.set_state(Booking.time)
        slots = await get_free_slots(day, data["service_id"])
        if slots:
            await call.message.edit_text(
                "😕 Это время только что заняли. Выбери другое:",
                reply_markup=kb.times_kb(slots),
            )
        else:
            await state.clear()
            await call.message.edit_text(
                "😕 Это время заняли, а свободных слотов на этот день больше нет.",
                reply_markup=kb.back_to_menu(),
            )
        await call.answer()
        return
    except LimitReached:
        await state.clear()
        await call.message.edit_text(
            "У тебя уже максимум активных записей. "
            "Отмени одну из них в разделе «Мои записи».",
            reply_markup=kb.back_to_menu(),
        )
        await call.answer()
        return

    await state.clear()
    await call.message.edit_text(
        f"✅ <b>Запись №{booking_id} подтверждена!</b>\n\n"
        f"{data['service_name']}\n"
        f"{day.strftime('%d.%m.%Y')} в {data['time']}\n\n"
        "Мы напомним о визите заранее. Ждём тебя!",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()

    # уведомление админам
    text = (
        f"🆕 <b>Новая запись №{booking_id}</b>\n"
        f"{data['service_name']}\n"
        f"{day.strftime('%d.%m.%Y')} в {data['time']}\n"
        f"{data['client_name']}, {data['phone']}"
    )
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            log.exception("Не удалось уведомить админа %s", admin_id)