"""
Signal Engine — core trade signal computation.

Rules (Plan-1.md):
  - Entry/target enforces minimum 2:1 reward-to-risk ratio.
  - SL = min(nearest S/R level distance, 1% of allocated capital per unit).
    'min' means the TIGHTER stop (smaller distance = less capital at risk).
  - Returns None if a valid signal cannot be constructed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["long", "short"]
MIN_RR_RATIO = 2.0


@dataclass
class TradeSignal:
    instrument: str
    direction: Direction
    entry: float
    stop_loss: float
    target: float
    risk_per_unit: float   # distance from entry to SL
    rr_ratio: float        # actual R:R (always >= MIN_RR_RATIO)
    capital_at_risk: float # total monetary risk for this trade


def _nearest_support(price: float, sr_levels: list[float]) -> float | None:
    """Return the closest S/R level strictly below price."""
    candidates = [lvl for lvl in sr_levels if lvl < price]
    return max(candidates) if candidates else None


def _nearest_resistance(price: float, sr_levels: list[float]) -> float | None:
    """Return the closest S/R level strictly above price."""
    candidates = [lvl for lvl in sr_levels if lvl > price]
    return min(candidates) if candidates else None


def compute_signal(
    instrument: str,
    direction: Direction,
    entry_price: float,
    sr_levels: list[float],
    capital_allocated: float,   # total INR/USD allocated to this trade
    quantity: int = 1,          # lot size or number of units
    min_rr_ratio: float = MIN_RR_RATIO,
) -> TradeSignal | None:
    """
    Compute a trade signal with enforced 2:1 R:R and dual-cap stop loss.

    Stop loss selection:
      sr_distance     = distance from entry to nearest S/R level
      capital_1pct    = 1% of capital_allocated / quantity  (max loss per unit)
      sl_distance     = min(sr_distance, capital_1pct)  — tighter stop wins

    Returns None when:
      - No valid S/R level exists AND capital-1% distance is zero/negative
      - Computed R:R < min_rr_ratio after applying SL
    """
    if entry_price <= 0 or capital_allocated <= 0 or quantity <= 0:
        return None

    # ── Compute the two candidate SL distances ────────────────────────────────
    max_loss_per_unit = (capital_allocated * 0.01) / quantity  # 1% of capital

    if direction == "long":
        sr_level = _nearest_support(entry_price, sr_levels)
        sr_distance = (entry_price - sr_level) if sr_level is not None else None
    else:
        sr_level = _nearest_resistance(entry_price, sr_levels)
        sr_distance = (sr_level - entry_price) if sr_level is not None else None

    # Choose the tighter (smaller) stop distance
    if sr_distance is not None and sr_distance > 0:
        sl_distance = min(sr_distance, max_loss_per_unit)
    elif max_loss_per_unit > 0:
        sl_distance = max_loss_per_unit
    else:
        return None  # cannot compute a valid stop

    if sl_distance <= 0:
        return None

    # ── Compute SL price and target ───────────────────────────────────────────
    if direction == "long":
        stop_loss = entry_price - sl_distance
        target = entry_price + (min_rr_ratio * sl_distance)
    else:
        stop_loss = entry_price + sl_distance
        target = entry_price - (min_rr_ratio * sl_distance)

    # ── Verify R:R ────────────────────────────────────────────────────────────
    reward = abs(target - entry_price)
    rr_ratio = reward / sl_distance

    if rr_ratio < min_rr_ratio:
        return None

    return TradeSignal(
        instrument=instrument,
        direction=direction,
        entry=round(entry_price, 4),
        stop_loss=round(stop_loss, 4),
        target=round(target, 4),
        risk_per_unit=round(sl_distance, 4),
        rr_ratio=round(rr_ratio, 4),
        capital_at_risk=round(sl_distance * quantity, 4),
    )
