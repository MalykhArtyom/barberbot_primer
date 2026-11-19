# 💈 BarberBot

Telegram-бот для автоматизации записи клиентов в барбершоп.

## Возможности

- Запись клиентов на стрижку.
- Просмотр доступной информации о записи.
- Управление записями через административную панель.
- Удобное меню с кнопками.
- Хранение данных в базе SQLite.

## Технологии

- Python 3
- Aiogram 3
- SQLite
- AioSQLite
- Python-dotenv

## Установка и запуск

1. Клонируйте репозиторий:

```bash
git clone https://github.com/MalykhArtyom/barberbot_primer.git
cd barberbot_primer
```

2. Создайте виртуальное окружение:

```bash
python -m venv venv
```

3. Активируйте его:

```bash
# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

4. Установите зависимости:

```bash
pip install -r requirements.txt
```

5. Создайте файл `.env` в корне проекта:

```env
BOT_TOKEN=your_bot_token
ADMIN_IDS=your_telegram_id
DB_PATH=barber.db
TIMEZONE=Asia/Yekaterinburg
```

При необходимости можно указать `PROXY_URL`.

6. Запустите бота:

```bash
python bot.py
```

## Структура проекта

```text
barberbot_primer/
├── handlers/       # Обработчики команд и сообщений
├── bot.py          # Точка входа
├── config.py       # Конфигурация
├── db.py           # Работа с базой данных
├── keyboards.py    # Клавиатуры бота
├── services.py     # Дополнительная логика
├── texts.py        # Тексты сообщений
├── requirements.txt
└── .env            # Переменные окружения
```

## Логи

Работа бота записывается в файл `bot.log`.

## Автор

[Artyom Malykh](https://github.com/MalykhArtyom)

---

*BarberBot — простой инструмент для удобной организации записи в барбершоп.*