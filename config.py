import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    proxy_url: str | None
    db_path: str
    timezone: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    admins = {
        int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    }
    return Config(
        bot_token=token,
        admin_ids=frozenset(admins),
        proxy_url=os.getenv("PROXY_URL") or None,
        db_path=os.getenv("DB_PATH", "barber.db"),
        timezone=os.getenv("TIMEZONE", "Asia/Yekaterinburg"),
    )


config = load_config()