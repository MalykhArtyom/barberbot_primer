import html

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import keyboards_admin as akb
from filters import IsAdmin
from services import (
    get_all_services, get_service_any, add_service,
    update_service, toggle_service,
)

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class AddService(StatesGroup):
    name = State()
    price = State()
    duration = State()


class EditService(StatesGroup):
    value = State()


FIELD_PROMPTS = {
    "name": "Введи новое <b>название</b> (2-40 символов):",
    "price": "Введи новую <b>цену</b> в рублях (число):",
    "duration": (
        "Введи новую <b>длительность</b> в минутах (15-480).\n"
        "Внимание: длительность влияет на занятость уже существующих записей."
    ),
}


# ---------- проверка ввода ----------
def parse_name(text: str) -> str | None:
    text = text.strip()
    return html.escape(text) if 2 <= len(text) <= 40 else None


def parse_price(text: str) -> int | None:
    text = text.strip()
    if text.isdigit() and 0 <= int(text) <= 100_000:
        return int(text)
    return None


def parse_duration(text: str) -> int | None:
    text = text.strip()
    if text.isdigit() and 15 <= int(text) <= 480:
        return int(text)
    return None


PARSERS = {"name": parse_name, "price": parse_price, "duration": parse_duration}
ERRORS = {
    "name": "Название должно быть от 2 до 40 символов.",
    "price": "Цена должна быть числом от 0 до 100000.",
    "duration": "Длительность должна быть числом от 15 до 480 минут.",
}


# ---------- экраны ----------
async def list_view():
    services = await get_all_services()
    text = (
        "💈 <b>Услуги</b>\n\n"
        "✅ доступна для записи, 🚫 отключена"
    )
    return text, akb.services_list_kb(services)


async def card_view(service_id: int):
    s = await get_service_any(service_id)
    if not s:
        return None
    status = "✅ доступна для записи" if s["is_active"] else "🚫 отключена"
    text = (
        f"💈 <b>{s['name']}</b>\n\n"
        f"Цена: {s['price']} ₽\n"
        f"Длительность: {s['duration_min']} мин\n"
        f"Статус: {status}"
    )
    return text, akb.service_card_kb(s)


@router.callback_query(F.data == "as:list")
async def show_list(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = await list_view()
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@router.callback_query(F.data.startswith("as:card:"))
async def show_card(call: CallbackQuery, state: FSMContext):
    await state.clear()
    view = await card_view(int(call.data.split(":")[2]))
    if not view:
        await call.answer("Услуга не найдена", show_alert=True)
        return
    await call.message.edit_text(view[0], reply_markup=view[1])
    await call.answer()


@router.callback_query(F.data.startswith("as:toggle:"))
async def toggle(call: CallbackQuery):
    service_id = int(call.data.split(":")[2])
    await toggle_service(service_id)
    view = await card_view(service_id)
    if not view:
        await call.answer("Услуга не найдена", show_alert=True)
        return
    await call.message.edit_text(view[0], reply_markup=view[1])
    await call.answer("Готово")


# ---------- редактирование ----------
@router.callback_query(F.data.startswith("as:edit:"))
async def start_edit(call: CallbackQuery, state: FSMContext):
    _, _, field, sid = call.data.split(":")
    if field not in PARSERS:
        await call.answer()
        return
    await state.set_state(EditService.value)
    await state.update_data(service_id=int(sid), field=field)
    await call.message.edit_text(
        FIELD_PROMPTS[field], reply_markup=akb.cancel_kb(f"as:card:{sid}")
    )
    await call.answer()


@router.message(EditService.value, F.text)
async def finish_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    field, service_id = data["field"], data["service_id"]
    value = PARSERS[field](message.text)
    if value is None:
        await message.answer(ERRORS[field] + " Попробуй ещё раз.")
        return
    await update_service(service_id, field, value)
    await state.clear()
    view = await card_view(service_id)
    await message.answer("✅ Сохранено.")
    await message.answer(view[0], reply_markup=view[1])


# ---------- добавление ----------
@router.callback_query(F.data == "as:add")
async def start_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddService.name)
    await call.message.edit_text(
        "➕ <b>Новая услуга</b>\n\nВведи название (2-40 символов):",
        reply_markup=akb.cancel_kb("as:list"),
    )
    await call.answer()


@router.message(AddService.name, F.text)
async def add_name(message: Message, state: FSMContext):
    name = parse_name(message.text)
    if name is None:
        await message.answer(ERRORS["name"] + " Попробуй ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(AddService.price)
    await message.answer(
        "Цена в рублях (число):", reply_markup=akb.cancel_kb("as:list")
    )


@router.message(AddService.price, F.text)
async def add_price(message: Message, state: FSMContext):
    price = parse_price(message.text)
    if price is None:
        await message.answer(ERRORS["price"] + " Попробуй ещё раз.")
        return
    await state.update_data(price=price)
    await state.set_state(AddService.duration)
    await message.answer(
        "Длительность в минутах (15-480):", reply_markup=akb.cancel_kb("as:list")
    )


@router.message(AddService.duration, F.text)
async def add_duration(message: Message, state: FSMContext):
    duration = parse_duration(message.text)
    if duration is None:
        await message.answer(ERRORS["duration"] + " Попробуй ещё раз.")
        return
    data = await state.get_data()
    service_id = await add_service(data["name"], data["price"], duration)
    await state.clear()
    view = await card_view(service_id)
    await message.answer("✅ Услуга добавлена.")
    await message.answer(view[0], reply_markup=view[1])