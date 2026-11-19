from db import connect


async def get_active_services() -> list[dict]:
    async with connect() as db:
        db.row_factory = __import__("aiosqlite").Row
        cur = await db.execute(
            "SELECT id, name, duration_min, price FROM services "
            "WHERE is_active = 1 ORDER BY id"
        )
        return [dict(r) for r in await cur.fetchall()]