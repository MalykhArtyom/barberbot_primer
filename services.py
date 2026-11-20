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

            start_dt = datetime.combine(day, datetime.strptime(time_, "%H:%M").time())
            until = start_dt - now_local()
            r24 = int(until <= timedelta(hours=24))
            r2 = int(until <= timedelta(hours=2))

            cur = await db.execute(
                "INSERT INTO bookings "
                "(user_id, service_id, date, time, client_name, phone, "
                " reminded_24h, reminded_2h) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, service_id, day.isoformat(), time_, name, phone, r24, r2),
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

async def get_bookings_by_date(day: date) -> list[dict]:
    async with connect() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT b.id, b.time, b.client_name, b.phone, "
            "       s.name AS service_name, s.duration_min "
            "FROM bookings b JOIN services s ON s.id = b.service_id "
            "WHERE b.date = ? AND b.status = 'active' "
            "ORDER BY b.time",
            (day.isoformat(),),
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_booking_counts(start: date, days: int) -> dict[str, int]:
    end = start + timedelta(days=days - 1)
    async with connect() as db:
        cur = await db.execute(
            "SELECT date, COUNT(*) FROM bookings "
            "WHERE status = 'active' AND date BETWEEN ? AND ? GROUP BY date",
            (start.isoformat(), end.isoformat()),
        )
        return {d: n for d, n in await cur.fetchall()}


async def admin_cancel_booking(booking_id: int) -> dict | None:
    """Отмена админом: без ограничения по времени. None, если уже отменена."""
    booking = await get_booking(booking_id)
    if not booking:
        return None
    async with connect() as db:
        cur = await db.execute(
            "UPDATE bookings SET status = 'cancelled' "
            "WHERE id = ? AND status = 'active'",
            (booking_id,),
        )
        await db.commit()
        if cur.rowcount == 0:
            return None
    return booking

# ---------- услуги (админ) ----------
_SERVICE_FIELDS = {"name": "name", "price": "price", "duration": "duration_min"}


async def get_all_services() -> list[dict]:
    async with connect() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, name, duration_min, price, is_active "
            "FROM services ORDER BY id"
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_service_any(service_id: int) -> dict | None:
    """Услуга независимо от того, включена она или нет."""
    async with connect() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, name, duration_min, price, is_active "
            "FROM services WHERE id = ?",
            (service_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_service(name: str, price: int, duration: int) -> int:
    async with connect() as db:
        cur = await db.execute(
            "INSERT INTO services (name, duration_min, price) VALUES (?, ?, ?)",
            (name, duration, price),
        )
        await db.commit()
        return cur.lastrowid


async def update_service(service_id: int, field: str, value) -> None:
    column = _SERVICE_FIELDS[field]  # только значения из белого списка
    async with connect() as db:
        await db.execute(
            f"UPDATE services SET {column} = ? WHERE id = ?", (value, service_id)
        )
        await db.commit()


async def toggle_service(service_id: int) -> None:
    async with connect() as db:
        await db.execute(
            "UPDATE services SET is_active = 1 - is_active WHERE id = ?",
            (service_id,),
        )
        await db.commit()


# ---------- расписание (админ) ----------
async def get_working_hours() -> list[dict]:
    async with connect() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT weekday, start_time, end_time, is_day_off "
            "FROM working_hours ORDER BY weekday"
        )
        return [dict(r) for r in await cur.fetchall()]


async def set_working_hours(weekday: int, start: str, end: str) -> None:
    async with connect() as db:
        await db.execute(
            "UPDATE working_hours SET start_time = ?, end_time = ?, is_day_off = 0 "
            "WHERE weekday = ?",
            (start, end, weekday),
        )
        await db.commit()


async def toggle_weekday(weekday: int) -> bool:
    """Переключает выходной/рабочий. Возвращает True, если день стал выходным."""
    async with connect() as db:
        cur = await db.execute(
            "SELECT is_day_off FROM working_hours WHERE weekday = ?", (weekday,)
        )
        is_off = (await cur.fetchone())[0]
        if is_off:
            # включаем день; если часов нет, ставим стандартные
            await db.execute(
                "UPDATE working_hours SET is_day_off = 0, "
                "start_time = COALESCE(start_time, '10:00'), "
                "end_time = COALESCE(end_time, '20:00') WHERE weekday = ?",
                (weekday,),
            )
        else:
            await db.execute(
                "UPDATE working_hours SET is_day_off = 1 WHERE weekday = ?",
                (weekday,),
            )
        await db.commit()
        return not is_off


async def count_future_bookings_on_weekday(weekday: int) -> int:
    today = now_local().date().isoformat()
    async with connect() as db:
        cur = await db.execute(
            "SELECT date FROM bookings WHERE status = 'active' AND date >= ?",
            (today,),
        )
        return sum(
            1 for (d,) in await cur.fetchall()
            if date.fromisoformat(d).weekday() == weekday
        )


async def get_future_days_off() -> list[date]:
    today = now_local().date().isoformat()
    async with connect() as db:
        cur = await db.execute(
            "SELECT date FROM days_off WHERE date >= ? ORDER BY date", (today,)
        )
        return [date.fromisoformat(d) for (d,) in await cur.fetchall()]


async def add_day_off(day: date) -> None:
    async with connect() as db:
        await db.execute(
            "INSERT OR IGNORE INTO days_off (date) VALUES (?)", (day.isoformat(),)
        )
        await db.commit()


async def remove_day_off(day: date) -> None:
    async with connect() as db:
        await db.execute("DELETE FROM days_off WHERE date = ?", (day.isoformat(),))
        await db.commit()

_REMINDER_COLUMNS = {"24h": "reminded_24h", "2h": "reminded_2h"}


async def get_pending_reminders() -> list[dict]:
    """Активные записи на сегодня и завтра, по которым ещё есть неотправленные напоминания."""
    today = now_local().date()
    async with connect() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT b.id, b.user_id, b.date, b.time, "
            "       b.reminded_24h, b.reminded_2h, s.name AS service_name "
            "FROM bookings b JOIN services s ON s.id = b.service_id "
            "WHERE b.status = 'active' AND b.date BETWEEN ? AND ? "
            "  AND (b.reminded_24h = 0 OR b.reminded_2h = 0)",
            (today.isoformat(), (today + timedelta(days=1)).isoformat()),
        )
        return [dict(r) for r in await cur.fetchall()]


async def claim_reminder(booking_id: int, kind: str) -> bool:
    """Атомарно «занимает» напоминание. True, если это сделали мы (можно отправлять)."""
    column = _REMINDER_COLUMNS[kind]
    async with connect() as db:
        cur = await db.execute(
            f"UPDATE bookings SET {column} = 1 "
            f"WHERE id = ? AND status = 'active' AND {column} = 0",
            (booking_id,),
        )
        await db.commit()
        return cur.rowcount == 1