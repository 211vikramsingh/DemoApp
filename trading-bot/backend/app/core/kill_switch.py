"""
Kill Switch engine — three scopes, all processed with highest priority.

Scopes:
  - global     : cancel ALL open orders + market-exit ALL positions for user
  - instrument : cancel/exit only a specific instrument
  - trade      : cancel/exit a single trade by ID

The kill command is dispatched to the high-priority `kill_queue` Celery queue
and also published to the Redis channel `kill:{user_id}` so all live strategy
workers immediately stop generating new signals.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import redis.asyncio as aioredis

from app.core.risk_manager import CircuitBreaker

logger = logging.getLogger(__name__)

KillScope = Literal["global", "instrument", "trade"]


@dataclass
class KillResult:
    scope: KillScope
    positions_closed: int
    orders_cancelled: int
    timestamp: datetime
    instrument: str | None = None
    trade_id: str | None = None
    partial_failure: bool = False          # True if one or more brokers reported failures
    failed_instruments: list[str] = None   # Which instruments could not be closed

    def __post_init__(self) -> None:
        if self.failed_instruments is None:
            self.failed_instruments = []


class KillSwitch:
    """
    Coordinates kill switch execution across broker adapters and Celery workers.
    Broker adapters are injected so the engine stays broker-agnostic.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        broker_registry: dict,  # {"kite": KiteAdapter, "delta": DeltaAdapter}
        user_id: str,
    ) -> None:
        self._r = redis_client
        self._brokers = broker_registry
        self._user_id = user_id
        self._circuit_breaker = CircuitBreaker(redis_client, user_id)

    # ── Public API ────────────────────────────────────────────────────────────

    async def execute_global(self) -> KillResult:
        """
        Cancel ALL orders and exit ALL positions for this user across all brokers.
        Returns a KillResult with partial_failure=True if any broker reported failures.
        Callers should inspect failed_instruments and alert the user to manually close.
        """
        positions_closed = 0
        orders_cancelled = 0
        all_failed: list[str] = []

        for broker_name, adapter in self._brokers.items():
            try:
                cancelled = await adapter.cancel_all_orders()
                # exit_all_positions now returns (count, failed_list)
                if isinstance(cancelled, tuple):
                    cancelled = cancelled[0]
                orders_cancelled += cancelled

                exit_result = await adapter.exit_all_positions()
                if isinstance(exit_result, tuple):
                    closed, failed = exit_result
                    positions_closed += closed
                    all_failed.extend(failed)
                else:
                    positions_closed += int(exit_result)
            except Exception:
                logger.exception("Kill switch: error in broker %s", broker_name)
                all_failed.append(broker_name)

        # Halt all strategy workers via Redis pub/sub
        await self._publish_kill_signal("global")

        # Set circuit breaker kill halt flag (blocks new signals)
        await self._circuit_breaker.set_kill_halt()

        partial = len(all_failed) > 0
        result = KillResult(
            scope="global",
            positions_closed=positions_closed,
            orders_cancelled=orders_cancelled,
            timestamp=datetime.now(timezone.utc),
            partial_failure=partial,
            failed_instruments=all_failed,
        )
        if partial:
            logger.error(
                "KILL SWITCH GLOBAL PARTIAL FAILURE — user=%s closed=%d cancelled=%d failed=%s",
                self._user_id, positions_closed, orders_cancelled, all_failed,
            )
        else:
            logger.warning(
                "KILL SWITCH GLOBAL — user=%s positions_closed=%d orders_cancelled=%d",
                self._user_id, positions_closed, orders_cancelled,
            )
        return result

    async def execute_instrument(self, instrument: str) -> KillResult:
        """
        Cancel orders and exit positions for one instrument only.
        instrument must be a non-empty string; validated before broker calls.
        """
        if not instrument or not instrument.strip():
            raise ValueError("instrument must be a non-empty string")

        positions_closed = 0
        orders_cancelled = 0
        all_failed: list[str] = []

        for broker_name, adapter in self._brokers.items():
            try:
                cancelled = await adapter.cancel_orders_for_instrument(instrument)
                closed = await adapter.exit_position_for_instrument(instrument)
                orders_cancelled += cancelled
                positions_closed += closed
            except Exception:
                logger.exception(
                    "Kill switch instrument %s: error in broker %s",
                    instrument, broker_name,
                )
                all_failed.append(broker_name)

        await self._publish_kill_signal(f"instrument:{instrument}")

        partial = len(all_failed) > 0
        result = KillResult(
            scope="instrument",
            positions_closed=positions_closed,
            orders_cancelled=orders_cancelled,
            timestamp=datetime.now(timezone.utc),
            instrument=instrument,
            partial_failure=partial,
            failed_instruments=all_failed,
        )
        logger.warning(
            "KILL SWITCH INSTRUMENT=%s — user=%s closed=%d cancelled=%d partial=%s",
            instrument, self._user_id, positions_closed, orders_cancelled, partial,
        )
        return result

    async def execute_trade(self, trade_id: str, instrument: str) -> KillResult:
        """
        Cancel or exit a single trade by ID.
        Validates both trade_id and instrument are non-empty.
        """
        if not trade_id or not trade_id.strip():
            raise ValueError("trade_id must be a non-empty string")
        if not instrument or not instrument.strip():
            raise ValueError("instrument must be a non-empty string")

        positions_closed = 0
        orders_cancelled = 0
        all_failed: list[str] = []

        for broker_name, adapter in self._brokers.items():
            try:
                result_flag = await adapter.exit_trade(trade_id, instrument)
                if result_flag:
                    # exit_trade closes position OR cancels order — count it once, not twice
                    positions_closed += 1
                else:
                    all_failed.append(broker_name)
            except Exception:
                logger.exception(
                    "Kill switch trade %s: error in broker %s",
                    trade_id, broker_name,
                )
                all_failed.append(broker_name)

        result = KillResult(
            scope="trade",
            positions_closed=positions_closed,
            orders_cancelled=orders_cancelled,
            timestamp=datetime.now(timezone.utc),
            trade_id=trade_id,
            partial_failure=len(all_failed) > 0,
            failed_instruments=all_failed,
        )
        logger.warning(
            "KILL SWITCH TRADE=%s instrument=%s — user=%s partial=%s",
            trade_id, instrument, self._user_id, result.partial_failure,
        )
        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _publish_kill_signal(self, payload: str) -> None:
        channel = f"kill:{self._user_id}"
        await self._r.publish(channel, payload)
