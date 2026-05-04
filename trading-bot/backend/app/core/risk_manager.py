"""
Circuit breaker for daily / weekly / monthly drawdown limits.
State is stored in Redis so it survives worker restarts.

Rules (from Plan-1.md):
  - Daily  : 3 SL hits in one calendar day  → halt all strategies
  - Weekly : rolling 5-trading-day drawdown ≥ 8%  → halt week
  - Monthly: calendar-month drawdown ≥ 15% → halt month (admin override required)
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

import redis.asyncio as aioredis

HaltReason = Literal["daily", "weekly", "monthly", "kill_switch", "none"]


class CircuitBreaker:
    """
    Per-user circuit-breaker backed by Redis.
    All keys are namespaced by user_id and date to avoid cross-user bleed.
    """

    def __init__(self, redis_client: aioredis.Redis, user_id: str) -> None:
        self._r = redis_client
        self._uid = user_id

    # ── Key helpers ───────────────────────────────────────────────────────────

    def _daily_sl_key(self) -> str:
        return f"cb:daily_sl:{self._uid}:{date.today().isoformat()}"

    def _daily_halt_key(self) -> str:
        return f"cb:daily_halt:{self._uid}:{date.today().isoformat()}"

    def _weekly_halt_key(self) -> str:
        iso_week = date.today().isocalendar()
        return f"cb:weekly_halt:{self._uid}:{iso_week.year}W{iso_week.week:02d}"

    def _monthly_halt_key(self) -> str:
        today = date.today()
        return f"cb:monthly_halt:{self._uid}:{today.year}-{today.month:02d}"

    def _kill_halt_key(self) -> str:
        return f"cb:kill_halt:{self._uid}"

    # ── SL hit recording ─────────────────────────────────────────────────────

    async def record_sl_hit(self) -> tuple[bool, HaltReason]:
        """
        Increments the daily SL counter.
        Returns (triggered, reason) — triggered=True means trading must halt.
        """
        key = self._daily_sl_key()
        count = await self._r.incr(key)
        await self._r.expire(key, 86_400)  # TTL: 24 h

        if count >= 3:
            await self._r.set(self._daily_halt_key(), "1", ex=86_400)
            return True, "daily"
        return False, "none"

    async def get_daily_sl_count(self) -> int:
        val = await self._r.get(self._daily_sl_key())
        return int(val) if val else 0

    # ── Drawdown checks ───────────────────────────────────────────────────────

    async def check_weekly_drawdown(self, drawdown_pct: float) -> tuple[bool, HaltReason]:
        """drawdown_pct should be negative (e.g. -0.09 for 9%)."""
        if drawdown_pct <= -0.08:
            await self._r.set(self._weekly_halt_key(), "1", ex=7 * 86_400)
            return True, "weekly"
        return False, "none"

    async def check_monthly_drawdown(self, drawdown_pct: float) -> tuple[bool, HaltReason]:
        if drawdown_pct <= -0.15:
            await self._r.set(self._monthly_halt_key(), "1", ex=35 * 86_400)
            return True, "monthly"
        return False, "none"

    # ── Kill switch flag ──────────────────────────────────────────────────────

    async def set_kill_halt(self) -> None:
        await self._r.set(self._kill_halt_key(), "1")

    async def clear_kill_halt(self) -> None:
        await self._r.delete(self._kill_halt_key())

    # ── Combined is_halted check (call before every signal) ──────────────────

    async def is_halted(self) -> tuple[bool, HaltReason]:
        """Returns (halted, reason). Reason 'none' means not halted."""
        if await self._r.exists(self._kill_halt_key()):
            return True, "kill_switch"
        if await self._r.exists(self._daily_halt_key()):
            return True, "daily"
        if await self._r.exists(self._weekly_halt_key()):
            return True, "weekly"
        if await self._r.exists(self._monthly_halt_key()):
            return True, "monthly"
        return False, "none"

    # ── Admin override (monthly only) ─────────────────────────────────────────

    async def admin_override_monthly(self) -> None:
        await self._r.delete(self._monthly_halt_key())

    async def manual_reset_daily(self) -> None:
        """Called at start of next trading day."""
        await self._r.delete(self._daily_halt_key())
        await self._r.delete(self._daily_sl_key())
