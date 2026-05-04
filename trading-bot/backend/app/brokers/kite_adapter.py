"""
Zerodha Kite Connect adapter.

Requires a valid Kite API key + secret (₹2000/month).
Access token expires daily — users must re-authenticate each morning.
See: https://kite.trade/docs/connect/v3/

Error classification:
  - Retryable  : network timeout, Kite TokenException (token expired) handled separately,
                 general NetworkException
  - Permanent  : InputException (bad symbol/params), OrderException (order rejected),
                 PermissionException (unauthorised)
"""
from __future__ import annotations

import logging
import time
from typing import Literal

from kiteconnect import KiteConnect
from kiteconnect.exceptions import (
    InputException,
    OrderException,
    NetworkException,
    TokenException,
    GeneralException,
)

from app.brokers.base import BrokerAdapter, OrderResult
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 3.0, 8.0]


def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, (NetworkException, GeneralException))


class KiteAdapter(BrokerAdapter):
    """
    Wraps kiteconnect.KiteConnect REST API.
    access_token must be set after Kite OAuth login flow (valid for one day).
    """

    EXCHANGE_NSE = KiteConnect.EXCHANGE_NSE
    EXCHANGE_NFO = KiteConnect.EXCHANGE_NFO
    PRODUCT_MIS = KiteConnect.PRODUCT_MIS    # intraday equity/F&O
    PRODUCT_NRML = KiteConnect.PRODUCT_NRML  # overnight / positional F&O
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

    def _call_with_retry(self, fn, *args, **kwargs):
        """
        Call a synchronous kiteconnect method with retry on transient errors.
        Raises the original exception for permanent errors.
        """
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except TokenException:
                # Token expired — cannot retry without user re-auth; raise immediately
                raise
            except (InputException, OrderException) as exc:
                # Permanent errors: bad symbol, bad params, order rejected
                logger.error("Kite permanent error on attempt %d: %s", attempt + 1, exc)
                raise
            except Exception as exc:
                if _is_retryable(exc):
                    wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
                    logger.warning(
                        "Kite transient error — retry %d/%d in %.1fs: %s",
                        attempt + 1, _MAX_RETRIES, wait, exc,
                    )
                    time.sleep(wait)
                    last_exc = exc
                else:
                    raise
        raise last_exc or RuntimeError("Kite API: max retries exhausted")

    # ── Order management ──────────────────────────────────────────────────────

    def _resolve_product(self, instrument: str, force_overnight: bool = False) -> str:
        """
        Use NRML for F&O instruments (contain expiry in symbol, e.g. NIFTY24DEC22000CE).
        Use MIS for intraday equity.
        """
        if force_overnight:
            return self.PRODUCT_NRML
        # F&O symbols contain digits + CE/PE/FUT — heuristic detection
        upper = instrument.upper()
        if upper.endswith("CE") or upper.endswith("PE") or upper.endswith("FUT"):
            return self.PRODUCT_NRML
        return self.PRODUCT_MIS

    async def place_market_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, force_overnight: bool = False
    ) -> OrderResult:
        product = self._resolve_product(instrument, force_overnight)
        try:
            order_id = self._call_with_retry(
                self._kite.place_order,
                variety=KiteConnect.VARIETY_REGULAR,
                exchange=self.EXCHANGE_NFO,
                tradingsymbol=instrument,
                transaction_type=(
                    KiteConnect.TRANSACTION_TYPE_BUY
                    if direction == "buy"
                    else KiteConnect.TRANSACTION_TYPE_SELL
                ),
                quantity=quantity,
                product=product,
                order_type=self.ORDER_TYPE_MARKET,
            )
            return OrderResult(order_id=str(order_id), status="placed",
                               instrument=instrument, quantity=quantity)
        except TokenException as e:
            msg = "Access token expired — user must re-authenticate"
            logger.error("Kite market order TokenException: %s", e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=msg)
        except (InputException, OrderException) as e:
            logger.error("Kite market order permanent failure %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))
        except Exception as e:
            logger.error("Kite market order failed %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def place_limit_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, limit_price: float, force_overnight: bool = False
    ) -> OrderResult:
        product = self._resolve_product(instrument, force_overnight)
        try:
            order_id = self._call_with_retry(
                self._kite.place_order,
                variety=KiteConnect.VARIETY_REGULAR,
                exchange=self.EXCHANGE_NFO,
                tradingsymbol=instrument,
                transaction_type=(
                    KiteConnect.TRANSACTION_TYPE_BUY if direction == "buy"
                    else KiteConnect.TRANSACTION_TYPE_SELL
                ),
                quantity=quantity,
                product=product,
                order_type=self.ORDER_TYPE_LIMIT,
                price=limit_price,
            )
            return OrderResult(order_id=str(order_id), status="placed",
                               instrument=instrument, quantity=quantity)
        except TokenException as e:
            return OrderResult(order_id="", status="rejected", instrument=instrument,
                               quantity=quantity, message="Token expired")
        except (InputException, OrderException) as e:
            logger.error("Kite limit order permanent failure %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))
        except Exception as e:
            logger.error("Kite limit order failed %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def place_sl_order(
        self, instrument: str, direction: Literal["buy", "sell"],
        quantity: int, trigger_price: float, limit_price: float,
        force_overnight: bool = False
    ) -> OrderResult:
        product = self._resolve_product(instrument, force_overnight)
        try:
            order_id = self._call_with_retry(
                self._kite.place_order,
                variety=KiteConnect.VARIETY_REGULAR,
                exchange=self.EXCHANGE_NFO,
                tradingsymbol=instrument,
                transaction_type=(
                    KiteConnect.TRANSACTION_TYPE_BUY if direction == "buy"
                    else KiteConnect.TRANSACTION_TYPE_SELL
                ),
                quantity=quantity,
                product=product,
                order_type=self.ORDER_TYPE_SLM,
                trigger_price=trigger_price,
                price=limit_price,
            )
            return OrderResult(order_id=str(order_id), status="placed",
                               instrument=instrument, quantity=quantity)
        except TokenException:
            return OrderResult(order_id="", status="rejected", instrument=instrument,
                               quantity=quantity, message="Token expired")
        except (InputException, OrderException) as e:
            logger.error("Kite SL order permanent failure %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))
        except Exception as e:
            logger.error("Kite SL order failed %s: %s", instrument, e)
            return OrderResult(order_id="", status="rejected",
                               instrument=instrument, quantity=quantity, message=str(e))

    async def cancel_order(self, order_id: str) -> bool:
        try:
            self._call_with_retry(
                self._kite.cancel_order,
                variety=KiteConnect.VARIETY_REGULAR,
                order_id=order_id,
            )
            return True
        except Exception as e:
            logger.error("Kite cancel order %s failed: %s", order_id, e)
            return False

    async def cancel_all_orders(self) -> int:
        orders = self._call_with_retry(self._kite.orders)
        cancelled = 0
        for o in orders:
            if o["status"] in ("OPEN", "PENDING", "TRIGGER PENDING"):
                if await self.cancel_order(o["order_id"]):
                    cancelled += 1
        return cancelled

    async def exit_all_positions(self) -> tuple[int, list[str]]:
        """
        Close all open net positions. Returns (closed_count, failed_instruments).
        Each position is closed independently; failures are reported rather than
        silently counted as success.
        """
        positions = self._call_with_retry(self._kite.positions)
        net = positions.get("net", [])
        closed = 0
        failed: list[str] = []

        for pos in net:
            qty = abs(pos.get("quantity", 0))
            if qty == 0:
                continue
            direction = "sell" if pos["quantity"] > 0 else "buy"
            symbol = pos["tradingsymbol"]
            result = await self.place_market_order(symbol, direction, qty)
            if result.status == "placed":
                closed += 1
            else:
                failed.append(symbol)
                logger.error("Kite exit_all: failed to close %s — %s", symbol, result.message)

        return closed, failed

    async def cancel_orders_for_instrument(self, instrument: str) -> int:
        orders = self._call_with_retry(self._kite.orders)
        cancelled = 0
        for o in orders:
            if (o["tradingsymbol"] == instrument
                    and o["status"] in ("OPEN", "PENDING", "TRIGGER PENDING")):
                if await self.cancel_order(o["order_id"]):
                    cancelled += 1
        return cancelled

    async def exit_position_for_instrument(self, instrument: str) -> int:
        positions = self._call_with_retry(self._kite.positions)
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
            closed = await self.exit_position_for_instrument(instrument)
            return closed > 0
        return True

    async def get_positions(self) -> list[dict]:
        return self._call_with_retry(self._kite.positions).get("net", [])

    async def get_account_balance(self) -> dict:
        margins = self._call_with_retry(self._kite.margins)
        return {
            "equity": margins.get("equity", {}),
            "commodity": margins.get("commodity", {}),
        }

    async def get_ltp(self, instrument: str) -> dict | None:
        """
        Returns the latest traded price for an index/equity instrument as a price dict
        compatible with the Redis price cache format.
        """
        try:
            exchange = "NSE"
            if instrument in ("NIFTY", "BANKNIFTY", "SENSEX"):
                exchange = "NSE" if instrument != "SENSEX" else "BSE"
            key = f"{exchange}:{instrument}"
            data = self._call_with_retry(self._kite.ltp, [key])
            ltp = data.get(key, {}).get("last_price", 0)
            if ltp > 0:
                return {"close": ltp, "open": ltp, "high": ltp, "low": ltp, "volume": 0}
            return None
        except Exception:
            return None

    async def get_option_chain(self, underlying: str) -> list[dict]:
        """
        Returns the options chain for an underlying (NIFTY, BANKNIFTY, SENSEX).
        Returns a list of strike dicts with: strike_price, option_type,
        underlying_price, days_to_expiry, iv, last_price, oi, volume.
        """
        try:
            instruments = self._call_with_retry(
                self._kite.instruments, exchange="NFO"
            )
            chain: list[dict] = []
            from datetime import date as _date
            today = _date.today()
            for inst in instruments:
                name = inst.get("name", "")
                segment = inst.get("segment", "")
                if name != underlying or segment != "NFO-OPT":
                    continue
                exp = inst.get("expiry")
                if exp is None:
                    continue
                days = (exp - today).days if hasattr(exp, "__sub__") else 0
                if days < 0:
                    continue
                chain.append({
                    "tradingsymbol": inst.get("tradingsymbol", ""),
                    "strike_price": float(inst.get("strike", 0)),
                    "option_type": inst.get("instrument_type", "CE"),
                    "underlying_price": 0.0,  # populated from LTP below
                    "days_to_expiry": days,
                    "iv": 0.20,  # placeholder; live IV requires tick data
                    "last_price": 0.0,
                    "oi": int(inst.get("oi", 0)),
                    "volume": 0,
                })
            # Limit to nearest two expiries to avoid overwhelming data volume
            expiry_days = sorted({c["days_to_expiry"] for c in chain})[:2]
            chain = [c for c in chain if c["days_to_expiry"] in expiry_days]
            return chain[:200]  # cap at 200 strikes
        except Exception:
            logger.warning("get_option_chain failed for %s", underlying, exc_info=True)
            return []


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
