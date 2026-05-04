"""
Kill Switch API endpoint.
POST /kill  — execute global / instrument / trade kill.
Dispatched to the high-priority kill_queue Celery queue.
"""
from __future__ import annotations
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, RedisClient
from app.core.kill_switch import KillSwitch, KillResult
from app.schemas import KillRequest, KillResponse

router = APIRouter(prefix="/kill", tags=["kill-switch"])


@router.post("/", response_model=KillResponse)
async def execute_kill(
    body: KillRequest,
    user: CurrentUser,
    redis: RedisClient,
) -> KillResponse:
    """
    Execute a kill switch command.

    Scopes:
      global     — cancel ALL orders + exit ALL positions
      instrument — cancel/exit for a specific instrument
      trade      — cancel/exit a single trade by ID

    This endpoint bypasses all circuit breakers and approval windows.
    After a global kill, all strategies are set to inactive.
    """
    # Broker registry — populated from user's stored (decrypted) API keys in production
    broker_registry: dict = {}  # {"kite": KiteAdapter(...), "delta": DeltaAdapter(...)}

    ks = KillSwitch(redis_client=redis, broker_registry=broker_registry, user_id=str(user.id))

    if body.scope == "global":
        result = await ks.execute_global()
    elif body.scope == "instrument":
        if not body.instrument:
            raise HTTPException(status_code=422, detail="instrument required for scope='instrument'")
        result = await ks.execute_instrument(body.instrument)
    else:  # trade
        if not body.trade_id:
            raise HTTPException(status_code=422, detail="trade_id required for scope='trade'")
        result = await ks.execute_trade(
            trade_id=body.trade_id,
            instrument=body.instrument or "",
        )

    return KillResponse(
        scope=result.scope,
        positions_closed=result.positions_closed,
        orders_cancelled=result.orders_cancelled,
        timestamp=result.timestamp,
        instrument=result.instrument,
        trade_id=result.trade_id,
    )
