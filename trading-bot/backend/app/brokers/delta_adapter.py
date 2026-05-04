"""
Delta Exchange adapter — BTC/ETH futures, options, and perpetuals.

API docs: https://docs.delta.exchange/
Funding rate endpoint: GET /v2/funding_rate
"""
from __future__ import annotations

import hashlib
import hmac
import time
import logging
from typing import Literal

import httpx

from app.brokers.base import BrokerAdapter, OrderResult
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DELTA_BASE_URL = settings.delta_base_url


class DeltaAdapter(BrokerAdapter):
    """
    Wraps Delta Exchange REST API.
    All requests are signed with HMAC-SHA256.
    """

    def __init__(self) -> None:
        self._api_key = settings.delta_api_key
        self._api_secret = settings.delta_api_secret
        self._client = httpx.AsyncClient(base_url=DELTA_BASE_URL, timeout=10.0)

    def _sign(self, method: str, path: str, body: str = "") -> dict:
        timestamp = str(int(time.time()))
        message = method + timestamp + path + body
        signature = hmac.new(
            self._api_secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return {
            "api-key": self._api_key,
            "timestamp": timestamp,
            "signature": signature,
            "Content-Type": "application/json",
        }

    async def place_market_order(
        self, instrument: str, direction: Literal["buy", "sell"], quantity: int
    ) -> OrderResult:
        path = "/v2/orders"
        payload = {
            "product_symbol": instrument,
            "size": quantity,
            "side": direction,
            "order_type": "market_order",
        }
        import json
        body = json.dumps(payload)
        headers = self._sign("POST", path, body)
        try:
            resp = await self._client.post(path, content=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            order_id = str(data.get("result", {}).get("id", ""))
            return OrderResult(order_id=order_id, status="placed",
                               instrument=instrument, quantity=quantity)
        except Exception as e:
            logger.error("Delta market order failed: %s", e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def place_limit_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, limit_price: float
    ) -> OrderResult:
        path = "/v2/orders"
        payload = {
            "product_symbol": instrument,
            "size": quantity,
            "side": direction,
            "order_type": "limit_order",
            "limit_price": str(limit_price),
        }
        import json
        body = json.dumps(payload)
        headers = self._sign("POST", path, body)
        try:
            resp = await self._client.post(path, content=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return OrderResult(
                order_id=str(data.get("result", {}).get("id", "")),
                status="placed", instrument=instrument, quantity=quantity,
            )
        except Exception as e:
            logger.error("Delta limit order failed: %s", e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def place_sl_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, trigger_price: float, limit_price: float
    ) -> OrderResult:
        # Delta Exchange uses bracket/stop-loss orders
        return await self.place_limit_order(instrument, direction, quantity, limit_price)

    async def cancel_order(self, order_id: str) -> bool:
        path = f"/v2/orders/{order_id}"
        headers = self._sign("DELETE", path)
        try:
            resp = await self._client.delete(path, headers=headers)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("Delta cancel order %s failed: %s", order_id, e)
            return False

    async def cancel_all_orders(self) -> int:
        path = "/v2/orders"
        headers = self._sign("DELETE", path)
        try:
            resp = await self._client.delete(path, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return len(data.get("result", []))
        except Exception as e:
            logger.error("Delta cancel all orders failed: %s", e)
            return 0

    async def exit_all_positions(self) -> int:
        positions = await self.get_positions()
        closed = 0
        for pos in positions:
            size = abs(int(pos.get("size", 0)))
            if size == 0:
                continue
            side = "sell" if int(pos.get("size", 0)) > 0 else "buy"
            result = await self.place_market_order(pos["product_symbol"], side, size)
            if result.status == "placed":
                closed += 1
        return closed

    async def cancel_orders_for_instrument(self, instrument: str) -> int:
        # Delta API supports filtering by product_symbol
        path = f"/v2/orders?product_symbol={instrument}"
        headers = self._sign("DELETE", path)
        try:
            resp = await self._client.delete(path, headers=headers)
            resp.raise_for_status()
            return len(resp.json().get("result", []))
        except Exception:
            return 0

    async def exit_position_for_instrument(self, instrument: str) -> int:
        positions = await self.get_positions()
        for pos in positions:
            if pos.get("product_symbol") == instrument:
                size = abs(int(pos.get("size", 0)))
                if size > 0:
                    side = "sell" if int(pos.get("size", 0)) > 0 else "buy"
                    result = await self.place_market_order(instrument, side, size)
                    return 1 if result.status == "placed" else 0
        return 0

    async def exit_trade(self, trade_id: str, instrument: str) -> bool:
        cancelled = await self.cancel_order(trade_id)
        if not cancelled:
            closed = await self.exit_position_for_instrument(instrument)
            return closed > 0
        return True

    async def get_positions(self) -> list[dict]:
        path = "/v2/positions/margined"
        headers = self._sign("GET", path)
        try:
            resp = await self._client.get(path, headers=headers)
            resp.raise_for_status()
            return resp.json().get("result", [])
        except Exception:
            return []

    async def get_account_balance(self) -> dict:
        path = "/v2/wallet/balances"
        headers = self._sign("GET", path)
        try:
            resp = await self._client.get(path, headers=headers)
            resp.raise_for_status()
            return resp.json().get("result", {})
        except Exception:
            return {}

    async def get_funding_rate(self, product_symbol: str) -> float | None:
        """Returns current funding rate for a perpetual product."""
        path = f"/v2/products/{product_symbol}/funding_rate"
        try:
            resp = await self._client.get(path)
            resp.raise_for_status()
            data = resp.json()
            rate = data.get("result", {}).get("funding_rate")
            return float(rate) if rate is not None else None
        except Exception:
            return None
