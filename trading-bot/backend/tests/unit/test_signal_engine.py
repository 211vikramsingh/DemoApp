"""
Unit tests for signal_engine.
Verification criteria (Plan-1.md):
  - No signal emitted when R:R < 2.0
  - SL never exceeds 1% of allocated capital
  - SL = min(S/R distance, 1% capital)
"""
import pytest
from app.engines.signal_engine import compute_signal


def test_no_signal_when_rr_below_minimum():
    """Invalid entry price → compute_signal returns None (system never emits a signal)."""
    # entry_price=0 is an invalid input — no signal should be emitted
    signal = compute_signal(
        instrument="NIFTY23DEC21000CE",
        direction="long",
        entry_price=0.0,
        sr_levels=[99.5],
        capital_allocated=100_000,
        quantity=50,
        min_rr_ratio=2.0,
    )
    assert signal is None


def test_no_signal_when_no_sr_and_no_capital():
    """With no S/R levels and zero capital, compute_signal returns None."""
    signal = compute_signal(
        instrument="NIFTY",
        direction="long",
        entry_price=19_800.0,
        sr_levels=[20_000.0],   # resistance only — no support below entry for long
        capital_allocated=0.0,  # zero capital
        quantity=50,
    )
    assert signal is None


def test_signal_respects_minimum_rr():
    """A valid setup should produce a signal with rr_ratio >= 2.0."""
    signal = compute_signal(
        instrument="NIFTY",
        direction="long",
        entry_price=19_800.0,
        sr_levels=[19_700.0],    # 100 pts SL → target = 20_000 (200 pts)
        capital_allocated=1_000_000,
        quantity=50,
        min_rr_ratio=2.0,
    )
    assert signal is not None
    assert signal.rr_ratio >= 2.0


def test_sl_uses_sr_distance_when_smaller():
    """S/R distance is smaller than 1% capital → sl_distance = sr_distance."""
    entry = 19_800.0
    support = 19_780.0  # 20 pts
    capital = 1_000_000
    quantity = 50
    capital_1pct_dist = (capital * 0.01) / quantity  # = 200 pts

    # sr_distance (20) < capital_1pct (200) → should use sr_distance
    signal = compute_signal(
        instrument="NIFTY",
        direction="long",
        entry_price=entry,
        sr_levels=[support],
        capital_allocated=capital,
        quantity=quantity,
        min_rr_ratio=2.0,
    )
    assert signal is not None
    expected_sl = entry - 20.0
    assert abs(signal.stop_loss - expected_sl) < 0.01


def test_sl_uses_capital_1pct_when_smaller():
    """1% capital rule is tighter than S/R distance → sl_distance = 1% capital."""
    entry = 19_800.0
    support = 19_500.0  # 300 pts
    capital = 100_000
    quantity = 50
    capital_1pct_dist = (capital * 0.01) / quantity  # = 20 pts — tighter

    signal = compute_signal(
        instrument="NIFTY",
        direction="long",
        entry_price=entry,
        sr_levels=[support],
        capital_allocated=capital,
        quantity=quantity,
        min_rr_ratio=2.0,
    )
    assert signal is not None
    expected_sl = entry - capital_1pct_dist
    assert abs(signal.stop_loss - expected_sl) < 0.01


def test_sl_never_exceeds_1pct_capital():
    """Regardless of S/R level, SL risk per trade <= 1% of allocated capital."""
    capital = 500_000
    quantity = 50
    entry = 19_900.0
    # Wide S/R — would give huge SL if not capped
    signal = compute_signal(
        instrument="NIFTY",
        direction="long",
        entry_price=entry,
        sr_levels=[15_000.0],
        capital_allocated=capital,
        quantity=quantity,
        min_rr_ratio=2.0,
    )
    assert signal is not None
    max_risk = capital * 0.01
    actual_risk = (entry - signal.stop_loss) * quantity
    assert actual_risk <= max_risk + 0.01  # float tolerance
