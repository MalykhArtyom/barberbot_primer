from datetime import date

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

WD_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def cancel_kb(callback_data: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ Отмена", callback_data=callback_data)
    return kb.as_markup()


# ---------- услуги ----------
def services_list_kb(services: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in services:
        mark = "✅" if s["is_active"] else "🚫"
        kb.button(
            text=f"{mark} {s['name']} · {s['price']} ₽ · {s['duration_min']} мин",
            callback_data=f"as:card:{s['id']}",
        )
    kb.button(text="➕ Добавить услугу", callback_data="as:add")
    kb.button(text="⬅️ Админ-меню", callback_data="adm:menu")
    kb.adjust(1)
    return kb.as_markup()


def service_card_kb(service: dict) -> InlineKeyboardMarkup:
    sid = service["id"]
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Название", callback_data=f"as:edit:name:{sid}")
    kb.button(text="💰 Цена", callback_data=f"as:edit:price:{sid}")
    kb.button(text="⏱ Длительность", callback_data=f"as:edit:duration:{sid}")
    kb.button(
        text="🚫 Отключить" if service["is_active"] else "✅ Включить",
        callback_data=f"as:toggle:{sid}",
    )
    kb.button(text="⬅️ К услугам", callback_data="as:list")
    kb.adjust(3, 1, 1)
    return kb.as_markup()


# ---------- расписание ----------
def schedule_kb(rows: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in rows:
        if r["is_day_off"] or not r["start_time"]:
            label = f"{WD_SHORT[r['weekday']]} · выходной"
        else:
            label = f"{WD_SHORT[r['weekday']]} · {r['start_time']}-{r['end_time']}"
        kb.button(text=label, callback_data=f"ash:wd:{r['weekday']}")
    kb.adjust(2)
    kb.button(text="📕 Выходные даты", callback_data="ash:off")
    kb.button(text="⬅️ Админ-меню", callback_data="adm:menu")
    kb.adjust(2, 2, 2, 1, 1, 1)
    return kb.as_markup()


def weekday_kb(row: dict) -> InlineKeyboardMarkup:
    wd = row["weekday"]
    kb = InlineKeyboardBuilder()
    kb.button(text="⏰ Изменить часы", callback_data=f"ash:hours:{wd}")
    kb.button(
        text="✅ Сделать рабочим" if row["is_day_off"] else "🛌 Сделать выходным",
        callback_data=f"ash:toggle:{wd}",
    )
    kb.button(text="⬅️ К расписанию", callback_data="ash:list")
    kb.adjust(1)
    return kb.as_markup()


def days_off_kb(days: list[date]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in days:
        kb.button(
            text=f"❌ {d.strftime('%d.%m.%Y')} ({WD_SHORT[d.weekday()]})",
            callback_data=f"ash:offdel:{d.isoformat()}",
        )
    kb.button(text="➕ Добавить дату", callback_data="ash:offadd")
    kb.button(text="⬅️ К расписанию", callback_data="ash:list")
    kb.adjust(1)
    return kb.as_markup()