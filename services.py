from db import connect
from datetime import date, datetime, timedelta

from zoneinfo import ZoneInfo
from config import config

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