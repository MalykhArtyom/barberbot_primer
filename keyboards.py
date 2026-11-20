from datetime import date, timedelta

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✂️ Записаться", callback_data="menu:book")
    kb.button(text="📋 Мои записи", callback_data="menu:my")
    kb.button(text="💈 Услуги и цены", callback_data="menu:services")
    kb.button(text="📍 Контакты", callback_data="menu:contacts")
    kb.adjust(1, 1, 2)
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    return kb.as_markup()


WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def services_kb(services: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in services:
        kb.button(
            text=f"{s['name']} · {s['price']} ₽",
            callback_data=f"svc:{s['id']}",
        )
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def dates_kb(dates: list[date]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in dates:
        kb.button(
            text=f"{WEEKDAYS[d.weekday()]} {d.strftime('%d.%m')}",
            callback_data=f"date:{d.isoformat()}",
        )
    kb.adjust(3)
    kb.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back:services"),
        InlineKeyboardButton(text="✖️ Отмена", callback_data="menu:main"),
    )
    return kb.as_markup()


def times_kb(slots: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in slots:
        kb.button(text=t, callback_data=f"time:{t}")
    kb.adjust(4)
    kb.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back:dates"),
        InlineKeyboardButton(text="✖️ Отмена", callback_data="menu:main"),
    )
    return kb.as_markup()

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def cancel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ Отмена", callback_data="menu:main")
    return kb.as_markup()


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Или введи номер вручную",
    )


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="confirm:yes")
    kb.button(text="✖️ Отмена", callback_data="menu:main")
    kb.adjust(2)
    return kb.as_markup()

WEEKDAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def my_bookings_kb(bookings: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in bookings:
        d = date.fromisoformat(b["date"])
        kb.button(
            text=f"{WEEKDAYS_RU[d.weekday()]} {d.strftime('%d.%m')} {b['time']} · {b['service_name']}",
            callback_data=f"mb:{b['id']}",
        )
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def booking_card_kb(booking_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отменить запись", callback_data=f"cx:{booking_id}")
    kb.button(text="⬅️ К моим записям", callback_data="menu:my")
    kb.adjust(1)
    return kb.as_markup()


def cancel_confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, отменить", callback_data=f"cxy:{booking_id}")
    kb.button(text="Нет, оставить", callback_data=f"mb:{booking_id}")
    kb.adjust(2)
    return kb.as_markup()

def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Сегодня", callback_data="adm:today")
    kb.button(text="📆 Завтра", callback_data="adm:tomorrow")
    kb.button(text="🗓 Другая дата", callback_data="adm:dates")
    kb.button(text="💈 Услуги", callback_data="as:list")
    kb.button(text="⏰ Расписание", callback_data="ash:list")
    kb.adjust(2, 1, 2)
    return kb.as_markup()


def admin_day_kb(day: date, bookings: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in bookings:
        kb.button(
            text=f"{b['time']} · {b['client_name']} · {b['service_name']}",
            callback_data=f"adm:b:{b['id']}",
        )
    kb.adjust(1)
    prev_d = day - timedelta(days=1)
    next_d = day + timedelta(days=1)
    kb.row(
        InlineKeyboardButton(text="◀️", callback_data=f"adm:day:{prev_d.isoformat()}"),
        InlineKeyboardButton(text="🗓 Дата", callback_data="adm:dates"),
        InlineKeyboardButton(text="▶️", callback_data=f"adm:day:{next_d.isoformat()}"),
    )
    kb.row(InlineKeyboardButton(text="⬅️ Админ-меню", callback_data="adm:menu"))
    return kb.as_markup()


def admin_dates_kb(days: list[date], counts: dict[str, int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in days:
        n = counts.get(d.isoformat(), 0)
        label = f"{WEEKDAYS[d.weekday()]} {d.strftime('%d.%m')}"
        if n:
            label += f" · {n}"
        kb.button(text=label, callback_data=f"adm:day:{d.isoformat()}")
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text="⬅️ Админ-меню", callback_data="adm:menu"))
    return kb.as_markup()


def admin_card_kb(booking_id: int, day_iso: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отменить запись", callback_data=f"adm:cx:{booking_id}")
    kb.button(text="⬅️ К списку дня", callback_data=f"adm:day:{day_iso}")
    kb.adjust(1)
    return kb.as_markup()


def admin_cancel_confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, отменить и уведомить", callback_data=f"adm:cxy:{booking_id}")
    kb.button(text="Нет", callback_data=f"adm:b:{booking_id}")
    kb.adjust(1)
    return kb.as_markup()


def admin_back_to_day_kb(day_iso: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ К списку дня", callback_data=f"adm:day:{day_iso}")
    return kb.as_markup()

def reminder_kb(booking_id: int, allow_cancel: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👍 Приду", callback_data=f"rem:ok:{booking_id}")
    if allow_cancel:
        kb.button(text="❌ Отменить", callback_data=f"cx:{booking_id}")
    kb.adjust(2)
    return kb.as_markup()