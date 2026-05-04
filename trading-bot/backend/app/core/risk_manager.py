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

    Thresholds can be overridden per-instance via the `settings` parameter,
    allowing different risk profiles per user/strategy.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        user_id: str,
        settings=None,
    ) -> None:
        self._r = redis_client
        self._uid = user_id
        # Import here to avoid circular imports at module load time
        if settings is None:
            from app.core.config import get_settings as _gs
            settings = _gs()
        self._daily_sl_limit: int = int(settings.daily_sl_limit)
        self._weekly_dd_pct: float = float(settings.weekly_drawdown_pct)
        self._monthly_dd_pct: float = float(settings.monthly_drawdown_pct)

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
        Threshold is configurable via settings.daily_sl_limit (default 3).
        """
        key = self._daily_sl_key()
        count = await self._r.incr(key)
        await self._r.expire(key, 86_400)  # TTL: 24 h

        if count >= self._daily_sl_limit:
            await self._r.set(self._daily_halt_key(), "1", ex=86_400)
            return True, "daily"
        return False, "none"

    async def get_daily_sl_count(self) -> int:
        val = await self._r.get(self._daily_sl_key())
        return int(val) if val else 0

    # ── Drawdown checks ───────────────────────────────────────────────────────

    async def check_weekly_drawdown(self, drawdown_pct: float) -> tuple[bool, HaltReason]:
        """
        drawdown_pct should be negative (e.g. -0.09 for 9%).
        Threshold is configurable via settings.weekly_drawdown_pct (default 0.08).
        """
        if drawdown_pct <= -abs(self._weekly_dd_pct):
            await self._r.set(self._weekly_halt_key(), "1", ex=7 * 86_400)
            return True, "weekly"
        return False, "none"

    async def check_monthly_drawdown(self, drawdown_pct: float) -> tuple[bool, HaltReason]:
        """
        drawdown_pct should be negative (e.g. -0.16 for 16%).
        Threshold is configurable via settings.monthly_drawdown_pct (default 0.15).
        """
        if drawdown_pct <= -abs(self._monthly_dd_pct):
            await self._r.set(self._monthly_halt_key(), "1", ex=35 * 86_400)
            return True, "monthly"
        return False, "none"

    async def compute_and_check_drawdown(
        self, current_balance: float, initial_balance: float
    ) -> tuple[bool, HaltReason]:
        """
        Compute drawdown from balances and check both weekly and monthly thresholds.
        Returns (halted, reason). Stores the drawdown pct in Redis for monitoring.
        """
        if initial_balance <= 0:
            return False, "none"
        drawdown_pct = (current_balance - initial_balance) / initial_balance
        # Store current drawdown pct for dashboard display
        await self._r.setex(
            f"cb:drawdown:{self._uid}:{date.today().isoformat()}",
            86_400,
            str(round(drawdown_pct, 6)),
        )
        halted, reason = await self.check_monthly_drawdown(drawdown_pct)
        if halted:
            return halted, reason
        return await self.check_weekly_drawdown(drawdown_pct)

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
