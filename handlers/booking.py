from datetime import date

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery

import keyboards as kb
from services import (
    get_active_services, get_service,
    get_available_dates, get_free_slots,
)

router = Router()


class Booking(StatesGroup):
    service = State()
    date = State()
    time = State()


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
    time_ = call.data.split(":", 1)[1]
    await state.update_data(time=time_)
    data = await state.get_data()
    await call.message.edit_text(
        "✅ Ты выбрал:\n\n"
        f"Услуга: {data['service_name']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {time_}\n\n"
        "Дальше (шаг 5) будет ввод имени и телефона и подтверждение.",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()