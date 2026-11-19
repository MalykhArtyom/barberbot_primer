from aiogram.types import InlineKeyboardMarkup
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