from app.engines.signal_engine import compute_signal, TradeSignal
from app.engines.kelly_sizer import kelly_fraction, vix_multiplier, get_position_size
from app.engines.max_pain import calculate_max_pain, pcr_signal
from app.engines.greeks_engine import black_scholes_greeks, implied_volatility, iv_percentile, Greeks
from app.engines.multi_leg_builder import (
    bull_call_spread, bear_put_spread, iron_condor, straddle, strangle, payoff_at_expiry
)
from app.engines.paper_trading import PaperTradingEngine, PaperWallet, PaperOrder

# BacktestEngine uses backtrader (C-extension). Import lazily to avoid
# breaking tests on hosts where backtrader is not installed.
try:
    from app.engines.backtesting_engine import BacktestEngine, BacktestResult  # noqa: F401
except ImportError:
    BacktestEngine = None  # type: ignore[assignment,misc]
    BacktestResult = None  # type: ignore[assignment]

__all__ = [
    "compute_signal", "TradeSignal",
    "kelly_fraction", "vix_multiplier", "get_position_size",
    "calculate_max_pain", "pcr_signal",
    "black_scholes_greeks", "implied_volatility", "iv_percentile", "Greeks",
    "bull_call_spread", "bear_put_spread", "iron_condor", "straddle", "strangle", "payoff_at_expiry",
    "PaperTradingEngine", "PaperWallet", "PaperOrder",
    "BacktestEngine", "BacktestResult",
]
