"""
Options Greeks engine using Black-Scholes (scipy).

Supports both Indian F&O (NSE risk-free rate) and
Delta Exchange crypto options (caller provides appropriate IV and r).

All theta values are returned as daily (per-calendar-day) theta.
Vega is per 1% (1 percentage point) change in IV.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm

# NSE risk-free rate (91-day T-bill; update periodically)
NSE_RISK_FREE_RATE = 0.065


@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float   # daily theta (INR/unit per day)
    vega: float    # per 1% IV change
    rho: float
    iv: float
    intrinsic_value: float
    time_value: float


def black_scholes_greeks(
    flag: str,     # 'c' for call, 'p' for put
    S: float,      # underlying spot price
    K: float,      # strike price
    t: float,      # time to expiry in years (e.g., 7/365)
    r: float,      # risk-free rate (e.g., 0.065)
    sigma: float,  # implied volatility (e.g., 0.18 for 18%)
) -> Greeks:
    """
    Compute Black-Scholes option price and all Greeks.
    Returns zeroed Greeks if expiry has passed (t ≤ 0).
    """
    if t <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return Greeks(delta=0, gamma=0, theta=0, vega=0, rho=0,
                      iv=sigma, intrinsic_value=0, time_value=0)

    sqrt_t = math.sqrt(t)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    nd1 = norm.cdf(d1)
    nd2 = norm.cdf(d2)
    nd1_neg = norm.cdf(-d1)
    nd2_neg = norm.cdf(-d2)
    pdf_d1 = norm.pdf(d1)
    discount = math.exp(-r * t)

    if flag == "c":
        price = S * nd1 - K * discount * nd2
        delta = nd1
        rho = K * t * discount * nd2 / 100
        intrinsic = max(0.0, S - K)
    else:  # put
        price = K * discount * nd2_neg - S * nd1_neg
        delta = nd1 - 1.0
        rho = -K * t * discount * nd2_neg / 100
        intrinsic = max(0.0, K - S)

    gamma = pdf_d1 / (S * sigma * sqrt_t)

    # Annual theta → daily theta
    if flag == "c":
        theta_annual = (
            -(S * pdf_d1 * sigma) / (2 * sqrt_t)
            - r * K * discount * nd2
        )
    else:
        theta_annual = (
            -(S * pdf_d1 * sigma) / (2 * sqrt_t)
            + r * K * discount * nd2_neg
        )
    theta_daily = theta_annual / 365

    # Vega per 1% change in vol
    vega = S * pdf_d1 * sqrt_t / 100

    time_value = max(0.0, price - intrinsic)

    return Greeks(
        delta=round(delta, 6),
        gamma=round(gamma, 6),
        theta=round(theta_daily, 6),
        vega=round(vega, 6),
        rho=round(rho, 6),
        iv=sigma,
        intrinsic_value=round(intrinsic, 4),
        time_value=round(time_value, 4),
    )


def implied_volatility(
    flag: str,
    market_price: float,
    S: float,
    K: float,
    t: float,
    r: float,
    tol: float = 1e-6,
    max_iterations: int = 200,
) -> float | None:
    """
    Compute implied volatility via bisection method.
    Returns None if IV cannot be found within bounds.
    """
    if t <= 0 or market_price <= 0:
        return None

    lo, hi = 0.001, 10.0  # 0.1% to 1000% IV search range

    for _ in range(max_iterations):
        mid = (lo + hi) / 2.0
        price = black_scholes_greeks(flag, S, K, t, r, mid)
        theo = price.intrinsic_value + price.time_value
        # Recompute full price from BS formula
        sqrt_t = math.sqrt(t)
        d1 = (math.log(S / K) + (r + 0.5 * mid ** 2) * t) / (mid * sqrt_t)
        d2 = d1 - mid * sqrt_t
        discount = math.exp(-r * t)
        if flag == "c":
            theo = S * norm.cdf(d1) - K * discount * norm.cdf(d2)
        else:
            theo = K * discount * norm.cdf(-d2) - S * norm.cdf(-d1)

        diff = theo - market_price
        if abs(diff) < tol:
            return round(mid, 6)
        if diff > 0:
            hi = mid
        else:
            lo = mid

    return None


def iv_percentile(current_iv: float, iv_history: list[float]) -> float:
    """
    Return the percentile rank of current_iv within iv_history (0–100).
    Used for IV percentile vs. 52-week range display.
    """
    if not iv_history:
        return 50.0
    below = sum(1 for v in iv_history if v <= current_iv)
    return round(100.0 * below / len(iv_history), 1)


def iv_skew_25delta(
    spot: float,
    t: float,
    r: float,
    call_25d_iv: float,
    put_25d_iv: float,
) -> float:
    """
    25-delta risk reversal skew = IV(25d call) - IV(25d put).
    Positive = call skew (market paying up for upside protection).
    Negative = put skew (market paying up for downside protection — typical for equities).
    """
    return round(call_25d_iv - put_25d_iv, 6)
