"""
Abstract broker adapter base class.
All broker implementations (Kite, Delta Exchange) must subclass this.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class OrderResult:
    order_id: str
    status: str          # 'placed' | 'rejected' | 'cancelled'
    instrument: str
    quantity: int
    fill_price: float | None = None
    message: str = ""


class BrokerAdapter(ABC):
    """Pluggable broker interface. Inject into KillSwitch and execution engine."""

    @abstractmethod
    async def place_market_order(
        self, instrument: str, direction: Literal["buy", "sell"], quantity: int
    ) -> OrderResult: ...

    @abstractmethod
    async def place_limit_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, limit_price: float
    ) -> OrderResult: ...

    @abstractmethod
    async def place_sl_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, trigger_price: float, limit_price: float
    ) -> OrderResult: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def cancel_all_orders(self) -> int:
        """Returns count of cancelled orders."""
        ...

    @abstractmethod
    async def exit_all_positions(self) -> int:
        """Market-exit all open positions. Returns count closed."""
        ...

    @abstractmethod
    async def cancel_orders_for_instrument(self, instrument: str) -> int: ...

    @abstractmethod
    async def exit_position_for_instrument(self, instrument: str) -> int: ...

    @abstractmethod
    async def exit_trade(self, trade_id: str, instrument: str) -> bool: ...

    @abstractmethod
    async def get_positions(self) -> list[dict]: ...

    @abstractmethod
    async def get_account_balance(self) -> dict: ...
