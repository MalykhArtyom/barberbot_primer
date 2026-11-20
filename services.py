from db import connect
from datetime import date, datetime, timedelta

from zoneinfo import ZoneInfo
from config import config

import aiosqlite

TZ = ZoneInfo(config.timezone)
SLOT_STEP_MIN = 30   # шаг сетки слотов
MIN_LEAD_MIN = 60    # минимум минут до визита

async def get_active_services() -> list[dict]:
    async with connect() as db:
        db.row_factory = __import__("aiosqlite").Row
        cur = await db.execute(
            "SELECT id, name, duration_min, price FROM services "
            "WHERE is_active = 1 ORDER BY id"
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_service(service_id: int) -> dict | None:
    async with connect() as db:
        db.row_factory = __import__("aiosqlite").Row
        cur = await db.execute(
            "SELECT id, name, duration_min, price FROM services "
            "WHERE id = ? AND is_active = 1",
            (service_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_available_dates(service_id: int, days_ahead: int = 14) -> list[date]:
    today = now_local().date()
    result = []
    for i in range(days_ahead):
        d = today + timedelta(days=i)
        if await get_free_slots(d, service_id):
            result.append(d)
    return result


async def get_free_slots(day: date, service_id: int) -> list[str]:
    service = await get_service(service_id)
    if not service:
        return []
    dur = service["duration_min"]

    async with connect() as db:
        cur = await db.execute(
            "SELECT start_time, end_time, is_day_off "
            "FROM working_hours WHERE weekday = ?",
            (day.weekday(),),
        )
        wh = await cur.fetchone()
        if not wh or wh[2] or not wh[0]:
            return []

        cur = await db.execute(
            "SELECT 1 FROM days_off WHERE date = ?", (day.isoformat(),)
        )
        if await cur.fetchone():
            return []

        # занятые интервалы: начало записи и её длительность по услуге
        cur = await db.execute(
            "SELECT b.time, s.duration_min "
            "FROM bookings b JOIN services s ON s.id = b.service_id "
            "WHERE b.date = ? AND b.status = 'active'",
            (day.isoformat(),),
        )
        busy = [(_to_min(t), _to_min(t) + d) for t, d in await cur.fetchall()]

    work_start, work_end = _to_min(wh[0]), _to_min(wh[1])

    earliest = 0
    now = now_local()
    if day == now.date():
        earliest = now.hour * 60 + now.minute + MIN_LEAD_MIN

    slots = []
    t = work_start
    while t + dur <= work_end:
        no_overlap = all(t + dur <= bs or t >= be for bs, be in busy)
        if t >= earliest and no_overlap:
            slots.append(_to_str(t))
        t += SLOT_STEP_MIN
    return slots

def now_local() -> datetime:
    """Текущее время в часовом поясе барбершопа (без tzinfo)."""
    return datetime.now(TZ).replace(tzinfo=None)


def _to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _to_str(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


MAX_ACTIVE_BOOKINGS = 3


class SlotTaken(Exception):
    """Слот уже занят или недоступен."""


class LimitReached(Exception):
    """У клиента слишком много активных записей."""


async def create_booking(
    user_id: int, service_id: int, day: date, time_: str,
    name: str, phone: str,
) -> int:
    service = await get_service(service_id)
    if not service:
        raise SlotTaken

    # слот должен быть в актуальной сетке (рабочие часы, запас по времени и т.д.)
    if time_ not in await get_free_slots(day, service_id):
        raise SlotTaken

    new_start = _to_min(time_)
    new_end = new_start + service["duration_min"]

    async with connect() as db:
        # BEGIN IMMEDIATE блокирует запись для других, пока идёт проверка
        await db.execute("BEGIN IMMEDIATE")
        try:
            cur = await db.execute(
                "SELECT COUNT(*) FROM bookings "
                "WHERE user_id = ? AND status = 'active' AND date >= ?",
                (user_id, now_local().date().isoformat()),
            )
            if (await cur.fetchone())[0] >= MAX_ACTIVE_BOOKINGS:
                raise LimitReached

            cur = await db.execute(
                "SELECT b.time, s.duration_min "
                "FROM bookings b JOIN services s ON s.id = b.service_id "
                "WHERE b.date = ? AND b.status = 'active'",
                (day.isoformat(),),
            )
            for t, d in await cur.fetchall():
                start = _to_min(t)
                if not (new_end <= start or new_start >= start + d):
                    raise SlotTaken

            cur = await db.execute(
                "INSERT INTO bookings "
                "(user_id, service_id, date, time, client_name, phone) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, service_id, day.isoformat(), time_, name, phone),
            )
            booking_id = cur.lastrowid
            await db.commit()
            return booking_id
        except aiosqlite.IntegrityError:
            await db.rollback()
            raise SlotTaken
        except BaseException:
            await db.rollback()
            raise

MIN_CANCEL_HOURS = 2


async def get_user_bookings(user_id: int) -> list[dict]:
    """Будущие активные записи клиента, ближайшие первыми."""
    now = now_local()
    async with connect() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT b.id, b.date, b.time, b.client_name, b.phone, "
            "       s.name AS service_name, s.price, s.duration_min "
            "FROM bookings b JOIN services s ON s.id = b.service_id "
            "WHERE b.user_id = ? AND b.status = 'active' AND b.date >= ? "
            "ORDER BY b.date, b.time",
            (user_id, now.date().isoformat()),
        )
        rows = [dict(r) for r in await cur.fetchall()]

    # отсекаем сегодняшние, которые уже прошли
    result = []
    for r in rows:
        start = datetime.fromisoformat(f"{r['date']} {r['time']}")
        if start > now:
            result.append(r)
    return result


async def get_booking(booking_id: int, user_id: int | None = None) -> dict | None:
    """Одна активная запись. Если передан user_id, проверяется владелец."""
    query = (
        "SELECT b.id, b.user_id, b.date, b.time, b.client_name, b.phone, "
        "       s.name AS service_name, s.price "
        "FROM bookings b JOIN services s ON s.id = b.service_id "
        "WHERE b.id = ? AND b.status = 'active'"
    )
    params: list = [booking_id]
    if user_id is not None:
        query += " AND b.user_id = ?"
        params.append(user_id)
    async with connect() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        row = await cur.fetchone()
        return dict(row) if row else None


class CancelTooLate(Exception):
    """До визита осталось слишком мало времени."""


async def cancel_booking(booking_id: int, user_id: int) -> dict | None:
    """Отмена клиентом. Возвращает запись или None, если её нет/уже отменена."""
    booking = await get_booking(booking_id, user_id)
    if not booking:
        return None

    start = datetime.fromisoformat(f"{booking['date']} {booking['time']}")
    if start - now_local() < timedelta(hours=MIN_CANCEL_HOURS):
        raise CancelTooLate

    async with connect() as db:
        cur = await db.execute(
            "UPDATE bookings SET status = 'cancelled' "
            "WHERE id = ? AND user_id = ? AND status = 'active'",
            (booking_id, user_id),
        )
        await db.commit()
        if cur.rowcount == 0:      # кто-то успел раньше
            return None
    return booking