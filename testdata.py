import sqlite3
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

con = sqlite3.connect("barber.db")
cmd = sys.argv[1] if len(sys.argv) > 1 else "show"

if cmd == "add":
    con.execute(
        "INSERT INTO bookings (user_id, service_id, date, time, client_name, phone) "
        "VALUES (1, 2, '2026-11-20', '12:00', 'Тест', '+70000000000')"
    )
    con.commit()
    print("Тестовая запись добавлена")
elif cmd == "delete":
    con.execute("DELETE FROM bookings WHERE client_name = 'Тест'")
    con.commit()
    print("Тестовые записи удалены")
elif cmd in ("remind24", "remind2"):
    tg_id = int(sys.argv[2])   # твой Telegram ID
    delta = (timedelta(hours=23, minutes=30) if cmd == "remind24"
             else timedelta(hours=1, minutes=30))
    start = datetime.now(ZoneInfo("Asia/Yekaterinburg")) + delta
    con.execute(
        "INSERT INTO bookings (user_id, service_id, date, time, client_name, phone) "
        "VALUES (?, 1, ?, ?, 'Тест', '+70000000000')",
        (tg_id, start.date().isoformat(), start.strftime("%H:%M")),
    )
    con.commit()
    print(f"Добавлена запись на {start:%d.%m %H:%M}")
else:
    for row in con.execute("SELECT * FROM bookings"):
        print(row)
