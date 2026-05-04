"""
Unit tests for multi_leg_builder.
Verification criteria (Plan-1.md):
  - Iron Condor: max_profit = net_premium, max_loss = wing_width − net_premium
  - Bull call spread max_loss = net debit paid
"""
import pytest
from app.engines.multi_leg_builder import (
    iron_condor, bull_call_spread, bear_put_spread, straddle,
    payoff_at_expiry,
)


def test_iron_condor_max_profit_equals_net_credit():
    strat = iron_condor(
        put_long_strike=17_000,
        put_short_strike=17_500,
        call_short_strike=18_500,
        call_long_strike=19_000,
        put_long_premium=50,
        put_short_premium=120,
        call_short_premium=110,
        call_long_premium=40,
        lot_size=50,
        expiry="2024-12-26",
    )
    expected_credit = (120 - 50) + (110 - 40)  # 70 + 70 = 140
    assert abs(strat.max_profit - expected_credit) < 0.01


def test_iron_condor_max_loss_equals_wing_minus_credit():
    strat = iron_condor(
        put_long_strike=17_000,
        put_short_strike=17_500,
        call_short_strike=18_500,
        call_long_strike=19_000,
        put_long_premium=50,
        put_short_premium=120,
        call_short_premium=110,
        call_long_premium=40,
        lot_size=50,
        expiry="2024-12-26",
    )
    wing_width = 17_500 - 17_000  # 500
    net_credit = (120 - 50) + (110 - 40)
    expected_max_loss = wing_width - net_credit
    assert abs(strat.max_loss - expected_max_loss) < 0.01


def test_bull_call_spread_max_loss_is_net_debit():
    strat = bull_call_spread(
        lower_strike=18_000,
        higher_strike=18_500,
        lower_call_premium=200,
        higher_call_premium=80,
        expiry="2024-12-26",
        lot_size=50,
    )
    net_debit = 200 - 80
    assert abs(strat.max_loss - net_debit) < 0.01


def test_straddle_breakevens_symmetric():
    strat = straddle(
        atm_strike=18_000,
        call_premium=300,
        put_premium=280,
        expiry="2024-12-26",
        lot_size=50,
    )
    net_cost = 300 + 280
    assert abs(strat.upper_breakeven - (18_000 + net_cost)) < 0.01
    assert abs(strat.lower_breakeven - (18_000 - net_cost)) < 0.01
