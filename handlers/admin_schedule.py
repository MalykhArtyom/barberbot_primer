import re
from datetime import date, datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import keyboards_admin as akb
from filters import IsAdmin
from services import (
    now_local, get_working_hours, set_working_hours, toggle_weekday,
    count_future_bookings_on_weekday, get_future_days_off,
    add_day_off, remove_day_off, get_bookings_by_date,
)

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

WD_FULL = ["Понедельник", "Вторник", "Среда", "Четверг",
           "Пятница", "Суббота", "Воскресенье"]
HOURS_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})$")


class EditHours(StatesGroup):
    value = State()


class AddDayOff(StatesGroup):
    value = State()


# ---------- разбор ввода ----------
def parse_hours(text: str) -> tuple[str, str] | None:
    m = HOURS_RE.match(text.strip())
    if not m:
        return None
    h1, m1, h2, m2 = map(int, m.groups())
    if not (0 <= h1 <= 23 and 0 <= h2 <= 23 and 0 <= m1 <= 59 and 0 <= m2 <= 59):
        return None
    if h1 * 60 + m1 >= h2 * 60 + m2:
        return None
    return f"{h1:02d}:{m1:02d}", f"{h2:02d}:{m2:02d}"


def parse_date(text: str, today: date) -> date | None:
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(text, fmt).date()
            return d if d >= today else None
        except ValueError:
            pass
    try:  # формат "25.12" без года
        d = datetime.strptime(f"{text}.{today.year}", "%d.%m.%Y").date()
        if d < today:
            d = d.replace(year=today.year + 1)
        return d
    except ValueError:
        return None


# ---------- экраны ----------
async def schedule_view():
    rows = await get_working_hours()
    return (
        "⏰ <b>Расписание</b>\n\nВыбери день недели, чтобы изменить часы "
        "или сделать его выходным:",
        akb.schedule_kb(rows),
    )


async def weekday_view(weekday: int):
    rows = await get_working_hours()
    row = next(r for r in rows if r["weekday"] == weekday)
    if row["is_day_off"] or not row["start_time"]:
        hours = "выходной"
    else:
        hours = f"{row['start_time']}-{row['end_time']}"
    return f"⏰ <b>{WD_FULL[weekday]}</b>\n\nСейчас: {hours}", akb.weekday_kb(row)


async def days_off_view():
    days = await get_future_days_off()
    text = "📕 <b>Выходные даты</b>\n\n"
    text += (
        "Нажми на дату, чтобы убрать её из выходных."
        if days else "Ближайших выходных дат нет."
    )
    return text, akb.days_off_kb(days)


# ---------- недельное расписание ----------
@router.callback_query(F.data == "ash:list")
async def show_schedule(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = await schedule_view()
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("ash:wd:"))
async def show_weekday(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = await weekday_view(int(call.data.split(":")[2]))
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("ash:toggle:"))
async def toggle(call: CallbackQuery):
    weekday = int(call.data.split(":")[2])
    became_off = await toggle_weekday(weekday)
    text, markup = await weekday_view(weekday)
    await call.message.edit_text(text, reply_markup=markup)

    if became_off:
        n = await count_future_bookings_on_weekday(weekday)
        if n:
            await call.answer(
                f"Внимание: на этот день недели уже есть записей: {n}. "
                "Они не отменены, проверь их в разделе дат.",
                show_alert=True,
            )
            return
    await call.answer("Готово")


@router.callback_query(F.data.startswith("ash:hours:"))
async def start_hours(call: CallbackQuery, state: FSMContext):
    weekday = int(call.data.split(":")[2])
    await state.set_state(EditHours.value)
    await state.update_data(weekday=weekday)
    await call.message.edit_text(
        f"⏰ <b>{WD_FULL[weekday]}</b>\n\n"
        "Введи часы работы в формате <code>10:00-20:00</code>:",
        reply_markup=akb.cancel_kb(f"ash:wd:{weekday}"),
    )
    await call.answer()


@router.message(EditHours.value, F.text)
async def finish_hours(message: Message, state: FSMContext):
    hours = parse_hours(message.text)
    if not hours:
        await message.answer(
            "Не получилось разобрать. Нужен формат <code>10:00-20:00</code>, "
            "начало раньше конца. Попробуй ещё раз."
        )
        return
    weekday = (await state.get_data())["weekday"]
    await set_working_hours(weekday, *hours)
    await state.clear()

    text, markup = await weekday_view(weekday)
    await message.answer("✅ Часы обновлены.")
    n = await count_future_bookings_on_weekday(weekday)
    if n:
        await message.answer(
            f"ℹ️ На этот день недели уже есть записей: {n}. "
            "Они не меняются, даже если выходят за новые часы."
        )
    await message.answer(text, reply_markup=markup)


# ---------- выходные даты ----------
@router.callback_query(F.data == "ash:off")
async def show_days_off(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = await days_off_view()
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("ash:offdel:"))
async def delete_day_off(call: CallbackQuery):
    await remove_day_off(date.fromisoformat(call.data.split(":")[2]))
    text, markup = await days_off_view()
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer("Убрано")


@router.callback_query(F.data == "ash:offadd")
async def start_day_off(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddDayOff.value)
    await call.message.edit_text(
        "Введи дату выходного: <code>25.12.2026</code> или просто <code>25.12</code>",
        reply_markup=akb.cancel_kb("ash:off"),
    )
    await call.answer()


@router.message(AddDayOff.value, F.text)
async def finish_day_off(message: Message, state: FSMContext):
    day = parse_date(message.text, now_local().date())
    if not day:
        await message.answer(
            "Не получилось разобрать дату или она уже прошла. "
            "Пример: <code>25.12.2026</code>. Попробуй ещё раз."
        )
        return
    await add_day_off(day)
    await state.clear()

    await message.answer(f"✅ {day.strftime('%d.%m.%Y')} добавлен в выходные.")
    existing = await get_bookings_by_date(day)
    if existing:
        await message.answer(
            f"⚠️ На эту дату уже есть записей: {len(existing)}. "
            "Они не отменены: открой день в разделе «Другая дата» и отмени вручную, "
            "тогда клиенты получат уведомление."
        )
    text, markup = await days_off_view()
    await message.answer(text, reply_markup=markup)