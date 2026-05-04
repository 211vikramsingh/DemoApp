"""
Kelly Criterion position sizing engine.

Formula (Plan-1.md):
  f* = (b·p − q) / b
  where:
    b = R:R ratio (reward per unit risked)
    p = win rate of the strategy (from backtest)
    q = 1 − p (loss rate)

Applied with half-Kelly (f*/2) for conservatism, then scaled by India VIX multiplier:
  VIX < 15  → ×1.0  (full size)
  VIX 15–20 → ×0.5  (half size)
  VIX ≥ 20  → ×0.0  (no new trades)

Hard caps:
  max 5%  of portfolio per single trade
  max 20% of portfolio per instrument
"""
from __future__ import annotations


def kelly_fraction(win_rate: float, rr_ratio: float) -> float:
    """
    Compute full Kelly fraction f*.
    Returns 0.0 if the edge is zero or negative (don't trade).

    Args:
        win_rate: probability of a winning trade (0–1), e.g. 0.55
        rr_ratio: reward-to-risk ratio, e.g. 2.0 for 2:1
    """
    if win_rate <= 0 or rr_ratio <= 0:
        return 0.0
    b = rr_ratio
    p = win_rate
    q = 1.0 - p
    f_star = (b * p - q) / b
    return max(0.0, f_star)


def vix_multiplier(vix: float) -> float:
    """Return the position-size multiplier based on India VIX level."""
    if vix >= 20.0:
        return 0.0
    if vix >= 15.0:
        return 0.5
    return 1.0


def get_position_size(
    win_rate: float,
    rr_ratio: float,
    portfolio_value: float,
    vix: float,
    method: str = "half_kelly",
    fixed_fraction: float = 0.02,
    max_single_trade_pct: float = 0.05,
    max_instrument_pct: float = 0.20,
    current_instrument_exposure: float = 0.0,
) -> float:
    """
    Return the INR/USD amount to allocate to a single trade.

    Args:
        win_rate:                  strategy win rate from backtesting (0–1)
        rr_ratio:                  expected reward-to-risk ratio
        portfolio_value:           total portfolio value in base currency
        vix:                       current India VIX (or crypto vol index)
        method:                    'half_kelly' | 'fixed'
        fixed_fraction:            fraction to use when method='fixed' (default 2%)
        max_single_trade_pct:      hard cap per trade as fraction of portfolio
        max_instrument_pct:        hard cap per instrument as fraction of portfolio
        current_instrument_exposure: already-allocated value in this instrument
    """
    mult = vix_multiplier(vix)
    if mult == 0.0 or portfolio_value <= 0:
        return 0.0

    if method == "fixed":
        fraction = fixed_fraction
    elif method == "kelly":
        fraction = kelly_fraction(win_rate, rr_ratio)  # full Kelly
    else:  # half_kelly (default)
        fraction = kelly_fraction(win_rate, rr_ratio) / 2.0  # half-Kelly

    # Apply VIX multiplier
    fraction *= mult

    # Apply single-trade cap
    fraction = min(fraction, max_single_trade_pct)

    position_size = fraction * portfolio_value

    # Apply per-instrument cap
    remaining_instrument_allowance = (
        max_instrument_pct * portfolio_value - current_instrument_exposure
    )
    position_size = min(position_size, max(0.0, remaining_instrument_allowance))

    return round(position_size, 2)
