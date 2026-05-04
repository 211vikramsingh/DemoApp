from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Trading Bot"
    debug: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://tradingbot:tradingbot@localhost:5432/tradingbot"
    )

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── JWT ───────────────────────────────────────────────────────────────────
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 hours — one trading session

    # ── AES-256 encryption key for broker API secrets ─────────────────────────
    encryption_key: str = "CHANGE_ME_32_BYTE_HEX"

    # ── Zerodha Kite Connect ──────────────────────────────────────────────────
    kite_api_key: str = ""
    kite_api_secret: str = ""

    # ── Delta Exchange ────────────────────────────────────────────────────────
    delta_api_key: str = ""
    delta_api_secret: str = ""
    delta_base_url: str = "https://api.delta.exchange"

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str = ""

    # ── Risk defaults (can be overridden per strategy) ────────────────────────
    max_single_trade_pct: float = 0.05   # 5% of portfolio per trade
    max_instrument_pct: float = 0.20     # 20% of portfolio per instrument
    daily_sl_limit: int = 3              # halt after 3 SL hits in a day
    weekly_drawdown_pct: float = 0.08    # halt if 8% rolling-5-day drawdown
    monthly_drawdown_pct: float = 0.15   # halt if 15% calendar-month drawdown

    # ── First run admin ───────────────────────────────────────────────────────
    first_run_admin_username: str = ""
    first_run_admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
