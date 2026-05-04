"""
Paper trading engine — simulates order execution with realistic slippage.

Maintains a virtual order book per user. No real broker connection required.
Dummy wallet is debited/credited on each simulated fill.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
import uuid

DEFAULT_SLIPPAGE_PCT = 0.0005  # 0.05%

OrderStatus = Literal["pending", "filled", "cancelled", "rejected"]


@dataclass
class PaperOrder:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    instrument: str = ""
    direction: Literal["long", "short"] = "long"
    order_type: Literal["market", "limit", "sl"] = "market"
    quantity: int = 0
    limit_price: float | None = None
    stop_price: float | None = None
    status: OrderStatus = "pending"
    fill_price: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: datetime | None = None
    slippage: float = 0.0


@dataclass
class PaperWallet:
    user_id: str
    initial_balance: float
    balance: float = field(default=-1.0)  # -1 sentinel → initialised in __post_init__
    realized_pnl: float = 0.0
    total_commission_paid: float = 0.0

    def __post_init__(self) -> None:
        # Use sentinel so that an explicit balance=0.0 is not overwritten
        if self.balance < 0:
            self.balance = self.initial_balance

    def debit(self, amount: float) -> bool:
        """Debit amount from wallet. Returns False if insufficient funds."""
        if amount < 0:
            raise ValueError(f"Debit amount must be non-negative, got {amount}")
        if amount > self.balance:
            return False
        self.balance -= amount
        return True

    def credit(self, amount: float) -> None:
        """Credit a realised P&L amount back to the wallet."""
        if amount < 0:
            raise ValueError(f"Credit amount must be non-negative, got {amount}")
        self.balance += amount
        self.realized_pnl += amount

    def charge_commission(self, commission: float) -> None:
        """Deduct brokerage commission from balance without affecting realized_pnl."""
        if commission < 0:
            raise ValueError(f"Commission must be non-negative, got {commission}")
        self.balance -= commission
        self.total_commission_paid += commission

    def reset(self) -> None:
        self.balance = self.initial_balance
        self.realized_pnl = 0.0
        self.total_commission_paid = 0.0


# Default commission rate (0.05% of trade value; adjust per broker)
DEFAULT_COMMISSION_PCT = 0.0005


class PaperTradingEngine:
    """
    Simulates order execution for paper trading.
    Applies realistic slippage and commission so P&L matches live trading more closely.
    Not thread-safe — intended to be used within a single async context.
    """

    def __init__(
        self,
        wallet: PaperWallet,
        slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
        commission_pct: float = DEFAULT_COMMISSION_PCT,
    ) -> None:
        self._wallet = wallet
        self._slippage_pct = slippage_pct
        self._commission_pct = commission_pct
        self._orders: dict[str, PaperOrder] = {}
        self._positions: dict[str, dict] = {}  # instrument → position

    # ── Order submission ──────────────────────────────────────────────────────

    def submit_market_order(
        self,
        instrument: str,
        direction: Literal["long", "short"],
        quantity: int,
        current_price: float,
    ) -> PaperOrder:
        slippage = current_price * self._slippage_pct
        if direction == "long":
            fill_price = current_price + slippage  # buying → slightly above market
        else:
            fill_price = current_price - slippage  # selling short → slightly below market

        cost = fill_price * quantity
        commission = cost * self._commission_pct

        # Check sufficient funds for both trade cost AND commission
        if not self._wallet.debit(cost):
            order = PaperOrder(
                instrument=instrument,
                direction=direction,
                order_type="market",
                quantity=quantity,
                status="rejected",
            )
            self._orders[order.id] = order
            return order

        # Deduct commission separately so realized_pnl tracking stays clean
        self._wallet.charge_commission(commission)

        order = PaperOrder(
            instrument=instrument,
            direction=direction,
            order_type="market",
            quantity=quantity,
            status="filled",
            fill_price=fill_price,
            filled_at=datetime.now(timezone.utc),
            slippage=slippage,
        )
        self._orders[order.id] = order
        self._update_position(instrument, direction, quantity, fill_price)
        return order

    def close_position(self, instrument: str, current_price: float) -> PaperOrder | None:
        pos = self._positions.get(instrument)
        if not pos:
            return None

        # Validate position dict has required keys before accessing
        direction = pos.get("direction")
        quantity = pos.get("quantity")
        avg_price = pos.get("avg_price")
        if direction is None or quantity is None or avg_price is None:
            return None

        slippage = current_price * self._slippage_pct
        if direction == "long":
            fill_price = current_price - slippage  # exiting long → sell at slight discount
            pnl = (fill_price - avg_price) * quantity
        else:
            fill_price = current_price + slippage  # exiting short → buy back at slight premium
            pnl = (avg_price - fill_price) * quantity

        # Return the original position cost + P&L; commission charged separately
        gross_proceeds = avg_price * quantity + pnl
        self._wallet.credit(max(0.0, gross_proceeds))  # can't credit negative

        # Commission on closing leg
        commission = fill_price * quantity * self._commission_pct
        self._wallet.charge_commission(commission)

        order = PaperOrder(
            instrument=instrument,
            direction="short" if direction == "long" else "long",
            order_type="market",
            quantity=quantity,
            status="filled",
            fill_price=fill_price,
            filled_at=datetime.now(timezone.utc),
            slippage=slippage,
        )
        self._orders[order.id] = order
        del self._positions[instrument]
        return order

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_position(
        self, instrument: str, direction: Literal["long", "short"], qty: int, price: float
    ) -> None:
        if instrument not in self._positions:
            self._positions[instrument] = {
                "direction": direction,
                "quantity": qty,
                "avg_price": price,
            }
        else:
            pos = self._positions[instrument]
            total_qty = pos["quantity"] + qty
            pos["avg_price"] = (pos["avg_price"] * pos["quantity"] + price * qty) / total_qty
            pos["quantity"] = total_qty

    def get_open_positions(self) -> dict:
        return dict(self._positions)

    def get_order(self, order_id: str) -> PaperOrder | None:
        return self._orders.get(order_id)
