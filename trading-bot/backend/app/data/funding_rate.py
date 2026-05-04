"""
Delta Exchange funding rate poller.

Polling interval: every 15 minutes during trading hours.
Carry filter thresholds (Plan-1.md):
  - funding_rate > +0.001 per 8h  → suppress LONG signals
  - funding_rate < -0.0005 per 8h → suppress SHORT signals
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

LONG_SUPPRESS_THRESHOLD  =  0.001    # +0.1% per 8h — longs paying heavy carry
SHORT_SUPPRESS_THRESHOLD = -0.0005   # -0.05% per 8h — shorts paying carry


def should_suppress_long(funding_rate: float) -> bool:
    return funding_rate > LONG_SUPPRESS_THRESHOLD


def should_suppress_short(funding_rate: float) -> bool:
    return funding_rate < SHORT_SUPPRESS_THRESHOLD


def carry_filter(direction: str, funding_rate: float) -> tuple[bool, str]:
    """
    Returns (suppressed, reason).
    direction: 'long' | 'short'
    """
    if direction == "long" and should_suppress_long(funding_rate):
        return True, f"funding_rate_carry: rate={funding_rate:.4%} > threshold (longs paying heavy carry)"
    if direction == "short" and should_suppress_short(funding_rate):
        return True, f"funding_rate_carry: rate={funding_rate:.4%} < threshold (shorts paying carry)"
    return False, ""
