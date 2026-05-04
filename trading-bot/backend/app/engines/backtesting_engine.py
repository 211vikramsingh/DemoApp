"""
Backtesting engine wrapper around backtrader.

Runs historical OHLCV replay for a strategy config and returns performance metrics:
  win_rate, expectancy, max_drawdown, sharpe_ratio, profit_factor,
  avg_trade_duration, total_trades, total_return_pct
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import backtrader as bt
import pandas as pd


@dataclass
class BacktestResult:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    expectancy: float        # avg profit per trade
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    total_return_pct: float
    avg_trade_duration_bars: float


class SimpleMovingAverageCrossStrategy(bt.Strategy):
    """
    Example backtrader strategy: EMA cross with configurable periods.
    Used as the default strategy skeleton — extend for full config-based strategies.
    """
    params = (
        ("fast_period", 9),
        ("slow_period", 21),
        ("stop_loss_pct", 0.01),
        ("rr_ratio", 2.0),
    )

    def __init__(self) -> None:
        self.ema_fast = bt.ind.EMA(period=self.params.fast_period)
        self.ema_slow = bt.ind.EMA(period=self.params.slow_period)
        self.crossover = bt.ind.CrossOver(self.ema_fast, self.ema_slow)
        self._entry_price: float | None = None
        self._trade_durations: list[int] = []
        self._trade_start_bar: int | None = None

    def next(self) -> None:
        if not self.position:
            if self.crossover > 0:  # bullish cross
                price = self.data.close[0]
                sl = price * (1 - self.params.stop_loss_pct)
                target = price + self.params.rr_ratio * (price - sl)
                self._entry_price = price
                self._trade_start_bar = len(self)
                self.buy()
        else:
            price = self.data.close[0]
            if self._entry_price:
                sl = self._entry_price * (1 - self.params.stop_loss_pct)
                target = self._entry_price + self.params.rr_ratio * (self._entry_price - sl)
                if price <= sl or price >= target or self.crossover < 0:
                    if self._trade_start_bar is not None:
                        self._trade_durations.append(len(self) - self._trade_start_bar)
                    self._entry_price = None
                    self._trade_start_bar = None
                    self.sell()


class BacktestEngine:
    """
    Wraps backtrader for OHLCV replay. Accepts a pandas DataFrame with columns:
    datetime, open, high, low, close, volume
    """

    def run(
        self,
        ohlcv_df: pd.DataFrame,
        strategy_params: dict[str, Any] | None = None,
        initial_cash: float = 1_000_000.0,
    ) -> BacktestResult:
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(initial_cash)
        cerebro.broker.setcommission(commission=0.0005)  # 0.05% commission

        # Add data feed
        data = bt.feeds.PandasData(dataname=ohlcv_df)
        cerebro.adddata(data)

        # Add strategy with params
        params = strategy_params or {}
        cerebro.addstrategy(SimpleMovingAverageCrossStrategy, **params)

        # Add analysers
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.065)
        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

        results = cerebro.run()
        strat = results[0]

        return self._extract_metrics(strat, initial_cash)

    def _extract_metrics(self, strat: bt.Strategy, initial_cash: float) -> BacktestResult:
        ta = strat.analyzers.trades.get_analysis()
        dd = strat.analyzers.drawdown.get_analysis()
        sharpe = strat.analyzers.sharpe.get_analysis()
        returns = strat.analyzers.returns.get_analysis()

        total = ta.get("total", {}).get("closed", 0)
        won = ta.get("won", {}).get("total", 0)
        lost = ta.get("lost", {}).get("total", 0)
        avg_win = ta.get("won", {}).get("pnl", {}).get("average", 0.0) or 0.0
        avg_loss = abs(ta.get("lost", {}).get("pnl", {}).get("average", 0.0) or 0.0)

        win_rate = (won / total) if total > 0 else 0.0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        gross_profit = ta.get("won", {}).get("pnl", {}).get("total", 0.0) or 0.0
        gross_loss = abs(ta.get("lost", {}).get("pnl", {}).get("total", 0.0) or 0.0)
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        max_dd_pct = dd.get("max", {}).get("drawdown", 0.0) or 0.0
        sharpe_val = sharpe.get("sharperatio") or 0.0
        total_return = returns.get("rtot", 0.0) or 0.0

        # Average trade duration
        avg_duration = 0.0
        if hasattr(strat, "_trade_durations") and strat._trade_durations:
            avg_duration = sum(strat._trade_durations) / len(strat._trade_durations)

        return BacktestResult(
            total_trades=total,
            winning_trades=won,
            losing_trades=lost,
            win_rate=round(win_rate, 4),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            expectancy=round(expectancy, 2),
            max_drawdown_pct=round(max_dd_pct, 4),
            sharpe_ratio=round(float(sharpe_val), 4) if sharpe_val else 0.0,
            profit_factor=round(profit_factor, 4),
            total_return_pct=round(float(total_return) * 100, 4),
            avg_trade_duration_bars=round(avg_duration, 1),
        )
