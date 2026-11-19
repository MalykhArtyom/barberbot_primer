import aiosqlite
from config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    duration_min INTEGER NOT NULL,
    price        INTEGER NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS working_hours (
    weekday    INTEGER PRIMARY KEY,      -- 0 = понедельник
    start_time TEXT,                     -- '10:00'
    end_time   TEXT,                     -- '20:00'
    is_day_off INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS days_off (
    date TEXT PRIMARY KEY                -- '2026-12-31'
);

CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    service_id   INTEGER NOT NULL REFERENCES services(id),
    date         TEXT    NOT NULL,       -- '2026-11-25'
    time         TEXT    NOT NULL,       -- '14:30'
    client_name  TEXT    NOT NULL,
    phone        TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'active',  -- active / cancelled
    reminded_24h INTEGER NOT NULL DEFAULT 0,
    reminded_2h  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- один активный слот = одна запись
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_slot
    ON bookings(date, time) WHERE status = 'active';
"""

DEFAULT_SERVICES = [
    ("Мужская стрижка", 60, 1500),
    ("Стрижка + борода", 90, 2200),
    ("Моделирование бороды", 30, 800),
    ("Детская стрижка", 45, 1000),
]


async def init_db() -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.executescript(SCHEMA)

        cur = await db.execute("SELECT COUNT(*) FROM services")
        if (await cur.fetchone())[0] == 0:
            await db.executemany(
                "INSERT INTO services (name, duration_min, price) VALUES (?, ?, ?)",
                DEFAULT_SERVICES,
            )

        cur = await db.execute("SELECT COUNT(*) FROM working_hours")
        if (await cur.fetchone())[0] == 0:
            # пн-сб 10:00-20:00, воскресенье выходной
            rows = [(d, "10:00", "20:00", 0) for d in range(6)]
            rows.append((6, None, None, 1))
            await db.executemany(
                "INSERT INTO working_hours VALUES (?, ?, ?, ?)", rows
            )

        await db.commit()


def connect() -> aiosqlite.Connection:
    """Использование: async with connect() as db: ..."""
    return aiosqlite.connect(config.db_path)