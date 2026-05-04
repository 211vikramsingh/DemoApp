"""
Multi-leg Options order builder.

Supported strategy templates:
  - Bull Call Spread  : buy lower-strike call + sell higher-strike call
  - Bear Put Spread   : buy higher-strike put + sell lower-strike put
  - Iron Condor       : sell put (short) + buy put (long wing)
                        + sell call (short) + buy call (long wing)
  - Straddle          : buy ATM call + buy ATM put (same strike)
  - Strangle          : buy OTM call + buy OTM put (different strikes)

Each template computes:
  net_premium, max_profit, max_loss, upper_breakeven, lower_breakeven
  (all in per-lot terms; multiply by lot_size for total monetary value)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

OptionType = Literal["call", "put"]
LegAction = Literal["buy", "sell"]


@dataclass
class Leg:
    action: LegAction        # 'buy' | 'sell'
    option_type: OptionType  # 'call' | 'put'
    strike: float
    premium: float           # per unit (lot size applied separately)
    expiry: str              # 'YYYY-MM-DD'


@dataclass
class MultiLegStrategy:
    strategy_type: str
    legs: list[Leg]
    net_premium: float       # positive = net debit paid; negative = net credit received
    max_profit: float        # per lot
    max_loss: float          # per lot (positive value, actual loss)
    upper_breakeven: float | None
    lower_breakeven: float | None
    lot_size: int = 1
    metadata: dict = field(default_factory=dict)

    @property
    def is_credit_strategy(self) -> bool:
        return self.net_premium < 0

    def total_max_profit(self) -> float:
        return self.max_profit * self.lot_size

    def total_max_loss(self) -> float:
        return self.max_loss * self.lot_size


# ── Strategy builders ─────────────────────────────────────────────────────────

def bull_call_spread(
    lower_strike: float,
    higher_strike: float,
    lower_call_premium: float,
    higher_call_premium: float,
    expiry: str,
    lot_size: int = 1,
) -> MultiLegStrategy:
    """
    Buy lower-strike call, sell higher-strike call.
    Max profit limited by spread width minus net debit.
    """
    net_debit = lower_call_premium - higher_call_premium
    spread_width = higher_strike - lower_strike
    max_profit = spread_width - net_debit
    max_loss = net_debit
    lower_breakeven = lower_strike + net_debit

    return MultiLegStrategy(
        strategy_type="bull_call_spread",
        legs=[
            Leg("buy",  "call", lower_strike,  lower_call_premium,  expiry),
            Leg("sell", "call", higher_strike, higher_call_premium, expiry),
        ],
        net_premium=net_debit,
        max_profit=max(0.0, max_profit),
        max_loss=max(0.0, max_loss),
        upper_breakeven=None,
        lower_breakeven=lower_breakeven,
        lot_size=lot_size,
    )


def bear_put_spread(
    higher_strike: float,
    lower_strike: float,
    higher_put_premium: float,
    lower_put_premium: float,
    expiry: str,
    lot_size: int = 1,
) -> MultiLegStrategy:
    """Buy higher-strike put, sell lower-strike put."""
    net_debit = higher_put_premium - lower_put_premium
    spread_width = higher_strike - lower_strike
    max_profit = spread_width - net_debit
    max_loss = net_debit
    upper_breakeven = higher_strike - net_debit

    return MultiLegStrategy(
        strategy_type="bear_put_spread",
        legs=[
            Leg("buy",  "put", higher_strike, higher_put_premium, expiry),
            Leg("sell", "put", lower_strike,  lower_put_premium,  expiry),
        ],
        net_premium=net_debit,
        max_profit=max(0.0, max_profit),
        max_loss=max(0.0, max_loss),
        upper_breakeven=upper_breakeven,
        lower_breakeven=None,
        lot_size=lot_size,
    )


def iron_condor(
    put_long_strike: float,
    put_short_strike: float,
    call_short_strike: float,
    call_long_strike: float,
    put_long_premium: float,
    put_short_premium: float,
    call_short_premium: float,
    call_long_premium: float,
    expiry: str,
    lot_size: int = 1,
) -> MultiLegStrategy:
    """
    Sell strangle (put_short + call_short) + buy wings (put_long + call_long).
    Net credit strategy. Max profit = net credit. Max loss = wing width − net credit.
    """
    net_credit = (put_short_premium - put_long_premium) + (call_short_premium - call_long_premium)
    put_wing_width = put_short_strike - put_long_strike
    call_wing_width = call_long_strike - call_short_strike
    wing_width = min(put_wing_width, call_wing_width)  # symmetric condor
    max_loss = wing_width - net_credit
    lower_breakeven = put_short_strike - net_credit
    upper_breakeven = call_short_strike + net_credit

    return MultiLegStrategy(
        strategy_type="iron_condor",
        legs=[
            Leg("buy",  "put",  put_long_strike,   put_long_premium,   expiry),
            Leg("sell", "put",  put_short_strike,  put_short_premium,  expiry),
            Leg("sell", "call", call_short_strike, call_short_premium, expiry),
            Leg("buy",  "call", call_long_strike,  call_long_premium,  expiry),
        ],
        net_premium=-net_credit,  # negative = credit received
        max_profit=max(0.0, net_credit),
        max_loss=max(0.0, max_loss),
        upper_breakeven=upper_breakeven,
        lower_breakeven=lower_breakeven,
        lot_size=lot_size,
    )


def straddle(
    atm_strike: float,
    call_premium: float,
    put_premium: float,
    expiry: str,
    lot_size: int = 1,
) -> MultiLegStrategy:
    """Buy ATM call + buy ATM put. Profits from large moves in either direction."""
    net_debit = call_premium + put_premium
    lower_breakeven = atm_strike - net_debit
    upper_breakeven = atm_strike + net_debit

    return MultiLegStrategy(
        strategy_type="straddle",
        legs=[
            Leg("buy", "call", atm_strike, call_premium, expiry),
            Leg("buy", "put",  atm_strike, put_premium,  expiry),
        ],
        net_premium=net_debit,
        max_profit=float("inf"),  # unlimited upside/downside
        max_loss=net_debit,
        upper_breakeven=upper_breakeven,
        lower_breakeven=lower_breakeven,
        lot_size=lot_size,
    )


def strangle(
    otm_call_strike: float,
    otm_put_strike: float,
    call_premium: float,
    put_premium: float,
    expiry: str,
    lot_size: int = 1,
) -> MultiLegStrategy:
    """Buy OTM call + buy OTM put. Cheaper than straddle, needs bigger move."""
    net_debit = call_premium + put_premium
    lower_breakeven = otm_put_strike - net_debit
    upper_breakeven = otm_call_strike + net_debit

    return MultiLegStrategy(
        strategy_type="strangle",
        legs=[
            Leg("buy", "call", otm_call_strike, call_premium, expiry),
            Leg("buy", "put",  otm_put_strike,  put_premium,  expiry),
        ],
        net_premium=net_debit,
        max_profit=float("inf"),
        max_loss=net_debit,
        upper_breakeven=upper_breakeven,
        lower_breakeven=lower_breakeven,
        lot_size=lot_size,
    )


def payoff_at_expiry(strategy: MultiLegStrategy, spot_at_expiry: float) -> float:
    """
    Compute the profit/loss per lot at a given spot price at expiry.
    Useful for generating the payoff diagram.
    """
    total = 0.0
    for leg in strategy.legs:
        if leg.option_type == "call":
            intrinsic = max(0.0, spot_at_expiry - leg.strike)
        else:
            intrinsic = max(0.0, leg.strike - spot_at_expiry)

        if leg.action == "buy":
            total += intrinsic - leg.premium
        else:
            total += leg.premium - intrinsic

    return round(total * strategy.lot_size, 4)
