"""
Delta Exchange adapter — BTC/ETH futures, options, and perpetuals.

API docs: https://docs.delta.exchange/
Funding rate endpoint: GET /v2/funding_rate

Error classification:
  - Retryable  : HTTP 429 (rate limit), 503/502/504 (server error), network timeout
  - Permanent  : HTTP 400 (bad request / invalid symbol), 401 (auth), 403 (forbidden)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Literal
from urllib.parse import quote

import httpx

from app.brokers.base import BrokerAdapter, OrderResult
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DELTA_BASE_URL = settings.delta_base_url

# HTTP status codes that warrant a retry with backoff
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 3.0, 8.0]  # seconds between retries


class BrokerOrderError(Exception):
    """Raised for permanent broker errors that should NOT be retried."""
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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
        # Use high-resolution timestamp to avoid signature collision within same second
        timestamp = str(int(time.time() * 1000))[:13]  # milliseconds as 13-digit string
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

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        body: str = "",
        **kwargs,
    ) -> httpx.Response:
        """
        Execute an HTTP request with retry on transient errors.
        Raises BrokerOrderError for permanent failures (4xx except 429).
        Raises httpx.HTTPError for exhausted retries on transient failures.
        """
        headers = self._sign(method, path, body)
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                if method == "GET":
                    resp = await self._client.get(path, headers=headers, **kwargs)
                elif method == "POST":
                    resp = await self._client.post(path, content=body, headers=headers, **kwargs)
                elif method == "DELETE":
                    resp = await self._client.delete(path, headers=headers, **kwargs)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                if resp.status_code in _RETRYABLE_STATUS:
                    wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
                    logger.warning(
                        "Delta API transient error %d on %s %s — retry %d/%d in %.1fs",
                        resp.status_code, method, path, attempt + 1, _MAX_RETRIES, wait,
                    )
                    time.sleep(wait)
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                    continue

                if resp.status_code >= 400:
                    # Permanent error — do not retry
                    raise BrokerOrderError(
                        f"Delta API error {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                    )

                return resp

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
                logger.warning(
                    "Delta API network error on %s %s — retry %d/%d in %.1fs: %s",
                    method, path, attempt + 1, _MAX_RETRIES, wait, exc,
                )
                time.sleep(wait)
                last_exc = exc

        raise last_exc or RuntimeError("Delta API: max retries exhausted")

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
        body = json.dumps(payload)
        try:
            resp = await self._request_with_retry("POST", path, body)
            data = resp.json()
            order_id = str(data.get("result", {}).get("id", ""))
            return OrderResult(order_id=order_id, status="placed",
                               instrument=instrument, quantity=quantity)
        except BrokerOrderError as e:
            logger.error("Delta market order permanent failure %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))
        except Exception as e:
            logger.error("Delta market order failed %s: %s", instrument, e)
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
        body = json.dumps(payload)
        try:
            resp = await self._request_with_retry("POST", path, body)
            data = resp.json()
            return OrderResult(
                order_id=str(data.get("result", {}).get("id", "")),
                status="placed", instrument=instrument, quantity=quantity,
            )
        except BrokerOrderError as e:
            logger.error("Delta limit order permanent failure %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))
        except Exception as e:
            logger.error("Delta limit order failed %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def place_sl_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, trigger_price: float, limit_price: float
    ) -> OrderResult:
        """
        Place a real stop-loss order on Delta Exchange using the stop_loss_order type.
        trigger_price is the price at which the order activates;
        limit_price is the worst accepted fill price.
        """
        path = "/v2/orders"
        payload = {
            "product_symbol": instrument,
            "size": quantity,
            "side": direction,
            "order_type": "stop_loss_order",
            "stop_price": str(trigger_price),
            "limit_price": str(limit_price),
        }
        body = json.dumps(payload)
        try:
            resp = await self._request_with_retry("POST", path, body)
            data = resp.json()
            order_id = str(data.get("result", {}).get("id", ""))
            logger.info(
                "Delta SL order placed: %s dir=%s qty=%d trigger=%.4f limit=%.4f id=%s",
                instrument, direction, quantity, trigger_price, limit_price, order_id,
            )
            return OrderResult(order_id=order_id, status="placed",
                               instrument=instrument, quantity=quantity)
        except BrokerOrderError as e:
            logger.error("Delta SL order permanent failure %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))
        except Exception as e:
            logger.error("Delta SL order failed %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def cancel_order(self, order_id: str) -> bool:
        path = f"/v2/orders/{order_id}"
        try:
            await self._request_with_retry("DELETE", path)
            return True
        except Exception as e:
            logger.error("Delta cancel order %s failed: %s", order_id, e)
            return False

    async def cancel_all_orders(self) -> int:
        path = "/v2/orders"
        try:
            resp = await self._request_with_retry("DELETE", path)
            data = resp.json()
            return len(data.get("result", []))
        except Exception as e:
            logger.error("Delta cancel all orders failed: %s", e)
            return 0

    async def exit_all_positions(self) -> tuple[int, list[str]]:
        """
        Close all open positions. Returns (closed_count, failed_instruments).
        Caller should check failed_instruments for partial failures.
        """
        positions = await self.get_positions()
        closed = 0
        failed: list[str] = []

        for pos in positions:
            size = abs(int(pos.get("size", 0)))
            if size == 0:
                continue
            side = "sell" if int(pos.get("size", 0)) > 0 else "buy"
            instrument = pos["product_symbol"]
            result = await self.place_market_order(instrument, side, size)
            if result.status == "placed":
                closed += 1
            else:
                failed.append(instrument)
                logger.error("Delta exit_all: failed to close %s — %s", instrument, result.message)

        return closed, failed

    async def cancel_orders_for_instrument(self, instrument: str) -> int:
        # URL-encode the instrument symbol to handle special chars like BTC/USD
        encoded = quote(instrument, safe="")
        path = f"/v2/orders?product_symbol={encoded}"
        try:
            resp = await self._request_with_retry("DELETE", path)
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
        try:
            resp = await self._request_with_retry("GET", path)
            return resp.json().get("result", [])
        except Exception:
            return []

    async def get_account_balance(self) -> dict:
        path = "/v2/wallet/balances"
        try:
            resp = await self._request_with_retry("GET", path)
            return resp.json().get("result", {})
        except Exception:
            return {}

    async def get_funding_rate(self, product_symbol: str) -> float | None:
        """Returns current funding rate for a perpetual product."""
        path = f"/v2/products/{quote(product_symbol, safe='')}/funding_rate"
        try:
            resp = await self._client.get(path)
            resp.raise_for_status()
            data = resp.json()
            rate = data.get("result", {}).get("funding_rate")
            return float(rate) if rate is not None else None
        except Exception:
            return None

    async def get_ticker(self, product_symbol: str) -> dict | None:
        """Returns latest ticker (last price, bid, ask) for an instrument."""
        path = f"/v2/tickers/{quote(product_symbol, safe='')}"
        try:
            resp = await self._client.get(path)
            resp.raise_for_status()
            result = resp.json().get("result", {})
            return {
                "close": float(result.get("close", 0)),
                "open": float(result.get("open", 0)),
                "high": float(result.get("high", 0)),
                "low": float(result.get("low", 0)),
                "volume": float(result.get("volume", 0)),
            }
        except Exception:
            return None
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
