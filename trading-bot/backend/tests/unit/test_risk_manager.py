"""
Unit tests for risk_manager CircuitBreaker.
Verification criteria (Plan-1.md):
  - 3rd SL hit triggers daily halt
  - 8% weekly drawdown triggers weekly halt
  - 15% monthly drawdown requires admin override
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.risk_manager import CircuitBreaker


def _make_cb(redis_data: dict | None = None) -> CircuitBreaker:
    """Create a CircuitBreaker with a fully async-mocked Redis client."""
    redis_data = redis_data or {}
    redis = MagicMock()

    async def _get(key):
        val = redis_data.get(key)
        return val.encode() if isinstance(val, str) else val

    async def _incr(key):
        redis_data[key] = int(redis_data.get(key, 0)) + 1
        return redis_data[key]

    async def _set(key, value, **kwargs):
        redis_data[key] = value

    async def _expire(key, ttl):
        pass  # no-op in tests

    async def _exists(key):
        return 1 if redis_data.get(key) else 0

    redis.get = _get
    redis.incr = _incr
    redis.set = _set
    redis.expire = _expire
    redis.exists = _exists
    return CircuitBreaker(redis, "user-test-1")


@pytest.mark.asyncio
async def test_third_sl_hit_triggers_halt():
    cb = _make_cb()
    triggered, reason = await cb.record_sl_hit()
    assert not triggered
    triggered, reason = await cb.record_sl_hit()
    assert not triggered
    triggered, reason = await cb.record_sl_hit()
    assert triggered
    assert reason == "daily"


@pytest.mark.asyncio
async def test_weekly_drawdown_triggers_halt():
    cb = _make_cb()
    halted, reason = await cb.check_weekly_drawdown(-0.09)
    assert halted
    assert reason == "weekly"


@pytest.mark.asyncio
async def test_weekly_drawdown_below_threshold_no_halt():
    cb = _make_cb()
    halted, _ = await cb.check_weekly_drawdown(-0.05)
    assert not halted


@pytest.mark.asyncio
async def test_monthly_drawdown_triggers_halt():
    cb = _make_cb()
    halted, reason = await cb.check_monthly_drawdown(-0.16)
    assert halted
    assert reason == "monthly"


@pytest.mark.asyncio
async def test_halted_after_daily_sl_limit():
    cb = _make_cb()
    await cb.record_sl_hit()
    await cb.record_sl_hit()
    await cb.record_sl_hit()
    is_halted = await cb.is_halted()
    assert is_halted
