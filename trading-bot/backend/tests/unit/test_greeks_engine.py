"""
Unit tests for greeks_engine (Black-Scholes via scipy).
Verification criteria (Plan-1.md):
  - ATM call delta ≈ 0.5
  - Deep ITM call delta ≈ 1.0
  - Theta is negative (time decay)
  - Vega is positive
  - Gamma peaks at ATM
"""
import pytest
import math
from app.engines.greeks_engine import black_scholes_greeks


def test_atm_call_delta_approx_half():
    """ATM call delta should be close to 0.5."""
    g = black_scholes_greeks("c", S=100, K=100, t=0.1, r=0.065, sigma=0.2)
    assert 0.45 <= g.delta <= 0.60


def test_deep_itm_call_delta_near_one():
    """Deep ITM call delta should approach 1.0."""
    g = black_scholes_greeks("c", S=150, K=100, t=0.5, r=0.065, sigma=0.2)
    assert g.delta > 0.90


def test_put_delta_negative():
    """Put delta is negative."""
    g = black_scholes_greeks("p", S=100, K=100, t=0.1, r=0.065, sigma=0.2)
    assert g.delta < 0


def test_theta_is_negative():
    """Theta (daily) must be negative — options lose time value each day."""
    g = black_scholes_greeks("c", S=100, K=100, t=0.1, r=0.065, sigma=0.2)
    assert g.theta < 0


def test_vega_is_positive():
    """Vega (per 1% IV change) must be positive."""
    g = black_scholes_greeks("c", S=100, K=100, t=0.1, r=0.065, sigma=0.2)
    assert g.vega > 0


def test_gamma_peaks_at_atm():
    """ATM gamma should be greater than deep ITM gamma."""
    atm = black_scholes_greeks("c", S=100, K=100, t=0.1, r=0.065, sigma=0.2)
    itm = black_scholes_greeks("c", S=200, K=100, t=0.1, r=0.065, sigma=0.2)
    assert atm.gamma > itm.gamma


def test_call_put_parity():
    """C - P = S * e^(-q*t) - K * e^(-r*t). With q=0: C - P ≈ S - K * e^(-r*t)."""
    S, K, t, r, sigma = 100, 100, 1.0, 0.065, 0.2
    call = black_scholes_greeks("c", S=S, K=K, t=t, r=r, sigma=sigma)
    put = black_scholes_greeks("p", S=S, K=K, t=t, r=r, sigma=sigma)
    # The greeks_engine stores iv (not price), so just verify delta consistency:
    # call.delta - put.delta ≈ 1.0 (put-call delta parity)
    diff = call.delta - put.delta
    assert abs(diff - 1.0) < 0.01
