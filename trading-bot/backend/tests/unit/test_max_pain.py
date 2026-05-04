"""
Unit tests for max_pain.
Verification criteria (Plan-1.md):
  - Known OI table produces known max pain strike
"""
import pytest
from app.engines.max_pain import calculate_max_pain, pcr_signal


# Constructed OI table where strike 18_000 has minimum total pain
KNOWN_OI_TABLE = [
    {"strike": 17_500, "call_oi": 50_000, "put_oi": 5_000},
    {"strike": 18_000, "call_oi": 5_000,  "put_oi": 5_000},   # balanced, lowest pain
    {"strike": 18_500, "call_oi": 5_000,  "put_oi": 50_000},
]


def test_max_pain_known_table():
    """Max pain strike for balanced OI at 18_000 should be 18_000."""
    result = calculate_max_pain(KNOWN_OI_TABLE)
    assert result == 18_000


def test_max_pain_single_strike():
    """Single-strike table returns that strike."""
    result = calculate_max_pain([{"strike": 20_000, "call_oi": 100, "put_oi": 200}])
    assert result == 20_000


def test_pcr_bullish_extreme():
    """PCR > 1.3 = bullish_extreme (too many puts → contrarian bullish)."""
    assert pcr_signal(131_000, 100_000) == "bullish_extreme"  # strictly > 1.3


def test_pcr_bearish_extreme():
    """PCR < 0.7 = bearish_extreme."""
    assert pcr_signal(60_000, 100_000) == "bearish_extreme"


def test_pcr_neutral():
    """PCR between 0.7 and 1.3 = neutral."""
    assert pcr_signal(100_000, 100_000) == "neutral"
