"""
Zerodha Kite Connect adapter.

Requires a valid Kite API key + secret (₹2000/month).
Access token expires daily — users must re-authenticate each morning.
See: https://kite.trade/docs/connect/v3/

NOTE: This is a production adapter stub. Full order flow is implemented;
WebSocket tick streaming requires a separate KiteTicker thread.
"""
from __future__ import annotations

import logging
from typing import Literal

from kiteconnect import KiteConnect

from app.brokers.base import BrokerAdapter, OrderResult
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class KiteAdapter(BrokerAdapter):
    """
    Wraps kiteconnect.KiteConnect REST API.
    access_token must be set after Kite OAuth login flow (valid for one day).
    """

    EXCHANGE_NSE = KiteConnect.EXCHANGE_NSE
    EXCHANGE_NFO = KiteConnect.EXCHANGE_NFO
    PRODUCT_MIS = KiteConnect.PRODUCT_MIS   # intraday
    PRODUCT_NRML = KiteConnect.PRODUCT_NRML # overnight / F&O
    ORDER_TYPE_MARKET = KiteConnect.ORDER_TYPE_MARKET
    ORDER_TYPE_LIMIT = KiteConnect.ORDER_TYPE_LIMIT
    ORDER_TYPE_SLM = KiteConnect.ORDER_TYPE_SLM

    def __init__(self, access_token: str | None = None) -> None:
        self._kite = KiteConnect(api_key=settings.kite_api_key)
        if access_token:
            self._kite.set_access_token(access_token)

    def set_access_token(self, token: str) -> None:
        self._kite.set_access_token(token)

    def get_login_url(self) -> str:
        return self._kite.login_url()

    def generate_session(self, request_token: str) -> dict:
        """Exchange request_token for access_token. Call once per day after login."""
        data = self._kite.generate_session(
            request_token, api_secret=settings.kite_api_secret
        )
        self._kite.set_access_token(data["access_token"])
        return data

    # ── Order management ──────────────────────────────────────────────────────

    async def place_market_order(
        self, instrument: str, direction: Literal["buy", "sell"], quantity: int
    ) -> OrderResult:
        try:
            order_id = self._kite.place_order(
                variety=KiteConnect.VARIETY_REGULAR,
                exchange=self.EXCHANGE_NFO,
                tradingsymbol=instrument,
                transaction_type=(
                    KiteConnect.TRANSACTION_TYPE_BUY
                    if direction == "buy"
                    else KiteConnect.TRANSACTION_TYPE_SELL
                ),
                quantity=quantity,
                product=self.PRODUCT_MIS,
                order_type=self.ORDER_TYPE_MARKET,
            )
            return OrderResult(order_id=str(order_id), status="placed",
                               instrument=instrument, quantity=quantity)
        except Exception as e:
            logger.error("Kite market order failed: %s", e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def place_limit_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, limit_price: float
    ) -> OrderResult:
        try:
            order_id = self._kite.place_order(
                variety=KiteConnect.VARIETY_REGULAR,
                exchange=self.EXCHANGE_NFO,
                tradingsymbol=instrument,
                transaction_type=(
                    KiteConnect.TRANSACTION_TYPE_BUY if direction == "buy"
                    else KiteConnect.TRANSACTION_TYPE_SELL
                ),
                quantity=quantity,
                product=self.PRODUCT_MIS,
                order_type=self.ORDER_TYPE_LIMIT,
                price=limit_price,
            )
            return OrderResult(order_id=str(order_id), status="placed",
                               instrument=instrument, quantity=quantity)
        except Exception as e:
            logger.error("Kite limit order failed: %s", e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def place_sl_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, trigger_price: float, limit_price: float
    ) -> OrderResult:
        try:
            order_id = self._kite.place_order(
                variety=KiteConnect.VARIETY_REGULAR,
                exchange=self.EXCHANGE_NFO,
                tradingsymbol=instrument,
                transaction_type=(
                    KiteConnect.TRANSACTION_TYPE_BUY if direction == "buy"
                    else KiteConnect.TRANSACTION_TYPE_SELL
                ),
                quantity=quantity,
                product=self.PRODUCT_MIS,
                order_type=self.ORDER_TYPE_SLM,
                trigger_price=trigger_price,
                price=limit_price,
            )
            return OrderResult(order_id=str(order_id), status="placed",
                               instrument=instrument, quantity=quantity)
        except Exception as e:
            logger.error("Kite SL order failed: %s", e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def cancel_order(self, order_id: str) -> bool:
        try:
            self._kite.cancel_order(variety=KiteConnect.VARIETY_REGULAR, order_id=order_id)
            return True
        except Exception as e:
            logger.error("Kite cancel order %s failed: %s", order_id, e)
            return False

    async def cancel_all_orders(self) -> int:
        orders = self._kite.orders()
        cancelled = 0
        for o in orders:
            if o["status"] in ("OPEN", "PENDING", "TRIGGER PENDING"):
                if await self.cancel_order(o["order_id"]):
                    cancelled += 1
        return cancelled

    async def exit_all_positions(self) -> int:
        positions = self._kite.positions()
        net = positions.get("net", [])
        closed = 0
        for pos in net:
            qty = abs(pos.get("quantity", 0))
            if qty == 0:
                continue
            direction = "sell" if pos["quantity"] > 0 else "buy"
            result = await self.place_market_order(pos["tradingsymbol"], direction, qty)
            if result.status == "placed":
                closed += 1
        return closed

    async def cancel_orders_for_instrument(self, instrument: str) -> int:
        orders = self._kite.orders()
        cancelled = 0
        for o in orders:
            if (o["tradingsymbol"] == instrument
                    and o["status"] in ("OPEN", "PENDING", "TRIGGER PENDING")):
                if await self.cancel_order(o["order_id"]):
                    cancelled += 1
        return cancelled

    async def exit_position_for_instrument(self, instrument: str) -> int:
        positions = self._kite.positions()
        for pos in positions.get("net", []):
            if pos["tradingsymbol"] == instrument:
                qty = abs(pos.get("quantity", 0))
                if qty > 0:
                    direction = "sell" if pos["quantity"] > 0 else "buy"
                    result = await self.place_market_order(instrument, direction, qty)
                    return 1 if result.status == "placed" else 0
        return 0

    async def exit_trade(self, trade_id: str, instrument: str) -> bool:
        result = await self.cancel_order(trade_id)
        if not result:
            # Try to exit as a position if it was already filled
            closed = await self.exit_position_for_instrument(instrument)
            return closed > 0
        return True

    async def get_positions(self) -> list[dict]:
        return self._kite.positions().get("net", [])

    async def get_account_balance(self) -> dict:
        margins = self._kite.margins()
        return {
            "equity": margins.get("equity", {}),
            "commodity": margins.get("commodity", {}),
        }
