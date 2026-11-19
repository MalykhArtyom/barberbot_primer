from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


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

from datetime import date

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