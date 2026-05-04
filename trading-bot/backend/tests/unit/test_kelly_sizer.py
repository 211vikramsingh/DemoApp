"""
Unit tests for kelly_sizer.
Verification criteria (Plan-1.md):
  - VIX >= 20 → position size = 0
  - Output matches f* = (b·p − q) / b formula
"""
import pytest
from app.engines.kelly_sizer import kelly_fraction, vix_multiplier, get_position_size


def test_kelly_formula():
    """f* = (b·p − q) / b where b = rr_ratio, p = win_rate, q = 1 - p."""
    win_rate = 0.6
    rr = 2.0
    b, p, q = rr, win_rate, 1 - win_rate
    expected = (b * p - q) / b
    assert abs(kelly_fraction(win_rate, rr) - expected) < 1e-9


def test_kelly_zero_for_losing_strategy():
    """Negative expectancy → kelly_fraction returns 0 (not negative)."""
    f = kelly_fraction(0.3, 1.0)  # 30% win rate, 1:1 R:R → negative
    assert f == 0.0


def test_vix_multiplier_low():
    assert vix_multiplier(12.0) == 1.0


def test_vix_multiplier_medium():
    assert vix_multiplier(17.0) == 0.5


def test_vix_multiplier_high():
    """VIX >= 20 → multiplier = 0 → position size = 0."""
    assert vix_multiplier(20.0) == 0.0
    assert vix_multiplier(25.0) == 0.0


def test_position_size_zero_at_high_vix():
    """get_position_size must return 0 when VIX >= 20."""
    size = get_position_size(
        win_rate=0.6,
        rr_ratio=2.0,
        portfolio_value=1_000_000,
        vix=25.0,
    )
    assert size == 0.0


def test_position_size_respects_max_single_trade_pct():
    """Position size capped at max_single_trade_pct (default 5%) of portfolio."""
    size = get_position_size(
        win_rate=0.9,
        rr_ratio=10.0,
        portfolio_value=1_000_000,
        vix=10.0,
        max_single_trade_pct=0.05,
    )
    assert size <= 1_000_000 * 0.05


def test_half_kelly_reduces_size():
    """Half-Kelly should return exactly half of full-Kelly result (caps disabled for comparison)."""
    full = get_position_size(
        0.6, 2.0, 1_000_000, 10.0, method="kelly",
        max_single_trade_pct=1.0, max_instrument_pct=1.0
    )
    half = get_position_size(
        0.6, 2.0, 1_000_000, 10.0, method="half_kelly",
        max_single_trade_pct=1.0, max_instrument_pct=1.0
    )
    assert full > 0, "Full Kelly should be positive"
    assert abs(half / full - 0.5) < 1e-6, f"Expected half={full/2:.2f}, got {half:.2f}"
