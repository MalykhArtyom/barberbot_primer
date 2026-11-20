import logging
from datetime import date, timedelta

from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from filters import IsAdmin
from services import (
    now_local, get_bookings_by_date, get_booking_counts,
    get_booking, admin_cancel_booking,
)

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
log = logging.getLogger(__name__)

WD = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
ADMIN_TITLE = "🛠 <b>Админ-панель</b>"


def fmt_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d.%m.%Y")


# ---------- вход ----------
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(ADMIN_TITLE, reply_markup=kb.admin_menu_kb())


@router.callback_query(F.data == "adm:menu")
async def to_admin_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(ADMIN_TITLE, reply_markup=kb.admin_menu_kb())
    await call.answer()


# ---------- записи за день ----------
async def render_day(call: CallbackQuery, day: date):
    bookings = await get_bookings_by_date(day)
    header = f"📅 <b>{WD[day.weekday()].capitalize()}, {day.strftime('%d.%m.%Y')}</b>\n\n"
    if bookings:
        lines = [
            f"{b['time']} ({b['duration_min']} мин) · {b['service_name']}\n"
            f"   {b['client_name']}, {b['phone']}"
            for b in bookings
        ]
        text = header + f"Записей: {len(bookings)}\n\n" + "\n\n".join(lines)
    else:
        text = header + "Записей нет."
    await call.message.edit_text(text, reply_markup=kb.admin_day_kb(day, bookings))


@router.callback_query(F.data == "adm:today")
async def show_today(call: CallbackQuery):
    await render_day(call, now_local().date())
    await call.answer()


@router.callback_query(F.data == "adm:tomorrow")
async def show_tomorrow(call: CallbackQuery):
    await render_day(call, now_local().date() + timedelta(days=1))
    await call.answer()


@router.callback_query(F.data.startswith("adm:day:"))
async def show_day(call: CallbackQuery):
    day = date.fromisoformat(call.data.split(":", 2)[2])
    await render_day(call, day)
    await call.answer()


@router.callback_query(F.data == "adm:dates")
async def pick_date(call: CallbackQuery):
    today = now_local().date()
    days = [today + timedelta(days=i) for i in range(21)]
    counts = await get_booking_counts(today, 21)
    await call.message.edit_text(
        "🗓 <b>Выбери дату</b> (число после точки: записей на день):",
        reply_markup=kb.admin_dates_kb(days, counts),
    )
    await call.answer()


# ---------- карточка записи ----------
@router.callback_query(F.data.startswith("adm:b:"))
async def show_card(call: CallbackQuery):
    b = await get_booking(int(call.data.split(":", 2)[2]))
    if not b:
        await call.answer("Запись не найдена или уже отменена", show_alert=True)
        return
    await call.message.edit_text(
        f"📋 <b>Запись №{b['id']}</b>\n\n"
        f"Услуга: {b['service_name']} ({b['price']} ₽)\n"
        f"Дата: {fmt_date(b['date'])}\n"
        f"Время: {b['time']}\n"
        f"Клиент: {b['client_name']}\n"
        f"Телефон: {b['phone']}",
        reply_markup=kb.admin_card_kb(b["id"], b["date"]),
    )
    await call.answer()


# ---------- отмена админом ----------
@router.callback_query(F.data.startswith("adm:cx:"))
async def ask_cancel(call: CallbackQuery):
    b = await get_booking(int(call.data.split(":", 2)[2]))
    if not b:
        await call.answer("Запись не найдена или уже отменена", show_alert=True)
        return
    await call.message.edit_text(
        f"Отменить запись №{b['id']}?\n"
        f"{b['client_name']}, {b['service_name']}, "
        f"{fmt_date(b['date'])} в {b['time']}\n\n"
        "Клиенту придёт уведомление.",
        reply_markup=kb.admin_cancel_confirm_kb(b["id"]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:cxy:"))
async def do_cancel(call: CallbackQuery, bot: Bot):
    b = await admin_cancel_booking(int(call.data.split(":", 2)[2]))
    if not b:
        await call.answer("Запись уже отменена", show_alert=True)
        return

    await call.message.edit_text(
        f"✅ Запись №{b['id']} отменена.",
        reply_markup=kb.admin_back_to_day_kb(b["date"]),
    )
    await call.answer()

    try:
        await bot.send_message(
            b["user_id"],
            "😔 К сожалению, твоя запись отменена барбершопом:\n"
            f"{b['service_name']}, {fmt_date(b['date'])} в {b['time']}.\n\n"
            "Можешь выбрать другое время через «Записаться» "
            "или связаться с нами по телефону.",
        )
    except Exception:
        log.warning("Не удалось уведомить клиента %s об отмене", b["user_id"])