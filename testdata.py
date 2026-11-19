import sqlite3
import sys

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
else:
    for row in con.execute("SELECT * FROM bookings"):
        print(row)