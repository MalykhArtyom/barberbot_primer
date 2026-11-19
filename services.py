from db import connect
from datetime import date, datetime, timedelta


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


async def get_available_dates(days_ahead: int = 14) -> list[date]:
    """Ближайшие рабочие дни (без выходных по расписанию и без days_off)."""
    async with connect() as db:
        cur = await db.execute(
            "SELECT weekday FROM working_hours WHERE is_day_off = 0"
        )
        workdays = {r[0] for r in await cur.fetchall()}
        cur = await db.execute("SELECT date FROM days_off")
        days_off = {r[0] for r in await cur.fetchall()}

    today = date.today()
    result = []
    for i in range(days_ahead):
        d = today + timedelta(days=i)
        if d.weekday() in workdays and d.isoformat() not in days_off:
            result.append(d)
    return result


async def get_free_slots(day: date, service_id: int) -> list[str]:
    """ЗАГЛУШКА. В шаге 4 заменим на реальный расчёт по расписанию и записям."""
    slots = [f"{h:02d}:00" for h in range(10, 20)]
    if day == date.today():
        now = datetime.now().strftime("%H:%M")
        slots = [s for s in slots if s > now]
    return slots