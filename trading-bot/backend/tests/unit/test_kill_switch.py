"""
Unit tests for kill_switch.
Verification criteria (Plan-1.md):
  - global / instrument / trade scopes all execute without error
  - KillResult contains correct scope
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.kill_switch import KillSwitch, KillResult


def _make_ks(positions: list[dict] | None = None) -> KillSwitch:
    redis = AsyncMock()
    broker = AsyncMock()
    broker.cancel_all_orders = AsyncMock(return_value=3)
    broker.exit_all_positions = AsyncMock(return_value=2)
    broker.cancel_orders_for_instrument = AsyncMock(return_value=1)
    broker.exit_position_for_instrument = AsyncMock(return_value=1)
    broker.cancel_order = AsyncMock(return_value=True)
    broker.exit_trade = AsyncMock(return_value=True)
    broker_registry = {"kite": broker}
    return KillSwitch(redis_client=redis, broker_registry=broker_registry, user_id="u1")


@pytest.mark.asyncio
async def test_global_kill_returns_correct_scope():
    ks = _make_ks()
    result = await ks.execute_global()
    assert isinstance(result, KillResult)
    assert result.scope == "global"


@pytest.mark.asyncio
async def test_instrument_kill_returns_correct_scope():
    ks = _make_ks()
    result = await ks.execute_instrument("NIFTY")
    assert result.scope == "instrument"
    assert result.instrument == "NIFTY"


@pytest.mark.asyncio
async def test_trade_kill_returns_correct_scope():
    ks = _make_ks()
    result = await ks.execute_trade(trade_id="order-123", instrument="BANKNIFTY")
    assert result.scope == "trade"
    assert result.trade_id == "order-123"
