"""
Live strategy worker — runs one Celery task per active strategy.

Loop:
  1. Check Redis kill channel — stop immediately if kill received.
  2. Check circuit breaker — skip signal generation if halted.
  3. Fetch latest price bar from Redis cache (written by data_worker).
  4. Call signal_engine.compute_signal() with cached S/R levels.
  5. Size the position with kelly_sizer.
  6. Execute via paper_trading (paper wallet) or broker adapter (live wallet).
  7. Persist the resulting Trade row and push a WebSocket notification.
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from app.workers.celery_app import app

logger = logging.getLogger(__name__)

# ── Polling interval (seconds between signal checks) ─────────────────────────
POLL_INTERVAL = 5  # check every 5 s; fast enough for NSE intraday


def _run_async(coro):
    """Run a coroutine from a synchronous Celery task without spawning a new thread."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already inside an event loop (e.g. gevent/eventlet workers): use nest_asyncio
            import nest_asyncio
            nest_asyncio.apply(loop)
            return loop.run_until_complete(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)


@app.task(bind=True, name="app.workers.strategy_worker.run_strategy", max_retries=3)
def run_strategy(self, strategy_id: str, user_id: str) -> dict:
    """
    Long-running strategy execution task.
    Subscribes to kill:{user_id} Redis channel; stops immediately on kill signal.
    Returns a summary dict on completion.
    """
    import redis as sync_redis
    from app.core.config import get_settings

    settings = get_settings()
    r = sync_redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(f"kill:{user_id}")

    logger.info("Strategy worker started: strategy_id=%s user_id=%s", strategy_id, user_id)

    signals_generated = 0
    trades_placed = 0
    last_heartbeat = time.monotonic()

    try:
        while True:
            # ── 1. Check for kill signal ──────────────────────────────────────
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.05)
            if message and message.get("type") == "message":
                payload = message.get("data", "")
                logger.warning(
                    "Kill signal received for user=%s payload=%s — stopping strategy %s",
                    user_id, payload, strategy_id,
                )
                pubsub.unsubscribe()
                return {
                    "status": "killed",
                    "strategy_id": strategy_id,
                    "signals_generated": signals_generated,
                    "trades_placed": trades_placed,
                }

            # ── 2. Heartbeat log every 60 s ───────────────────────────────────
            now = time.monotonic()
            if now - last_heartbeat >= 60:
                logger.info(
                    "Strategy heartbeat: strategy_id=%s signals=%d trades=%d",
                    strategy_id, signals_generated, trades_placed,
                )
                last_heartbeat = now

            # ── 3. Run signal + execution logic ──────────────────────────────
            result = _run_async(
                _execute_strategy_tick(
                    r=r,
                    strategy_id=strategy_id,
                    user_id=user_id,
                    settings=settings,
                )
            )
            if result == "signal":
                signals_generated += 1
            elif result == "trade":
                signals_generated += 1
                trades_placed += 1

            # ── 4. Non-blocking sleep ─────────────────────────────────────────
            time.sleep(POLL_INTERVAL)

    except Exception as exc:
        logger.exception("Strategy worker error: strategy_id=%s", strategy_id)
        raise self.retry(exc=exc, countdown=10)
    finally:
        pubsub.close()
        r.close()


async def _execute_strategy_tick(
    r,
    strategy_id: str,
    user_id: str,
    settings,
) -> str:
    """
    Single tick: check circuit breaker → fetch data → compute signal → execute.
    Returns 'signal' | 'trade' | 'skipped'.
    """
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import select

    from app.core.risk_manager import CircuitBreaker
    from app.engines.signal_engine import compute_signal
    from app.engines.kelly_sizer import KellySizer, PositionSizeRequest
    from app.engines.paper_trading import PaperTradingEngine, PaperWallet
    from app.models.strategy import Strategy
    from app.models.trade import Trade
    from app.models.wallet import Wallet

    async_r = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        # ── Circuit breaker check ─────────────────────────────────────────────
        cb = CircuitBreaker(async_r, user_id, settings=settings)
        halted, reason = await cb.is_halted()
        if halted:
            logger.debug("Strategy %s skipped — circuit breaker: %s", strategy_id, reason)
            return "skipped"

        # ── Load strategy config from Redis cache (avoids DB hit every tick) ──
        cached_str = r.get(f"strategy_cfg:{strategy_id}")
        if not cached_str:
            # Fall back to DB on cache miss
            engine = create_async_engine(settings.database_url, echo=False)
            async with AsyncSession(engine) as session:
                strat = await session.get(Strategy, uuid.UUID(strategy_id))
                if strat is None or not strat.is_active:
                    return "skipped"
                config = strat.config
                wallet_type = strat.wallet_type
                sizing_method = strat.position_sizing_method
                # Cache for 60 s
                r.setex(
                    f"strategy_cfg:{strategy_id}",
                    60,
                    json.dumps({"config": config, "wallet_type": wallet_type, "sizing": sizing_method}),
                )
            await engine.dispose()
        else:
            cached = json.loads(cached_str)
            config = cached["config"]
            wallet_type = cached["wallet_type"]
            sizing_method = cached["sizing"]

        # ── Fetch latest price bar from Redis (written by data_worker) ────────
        instrument = config.get("instrument", "NIFTY")
        price_key = f"price:{instrument}:latest"
        price_raw = r.get(price_key)
        if not price_raw:
            logger.debug("No price data cached for %s — skipping tick", instrument)
            return "skipped"

        price_data = json.loads(price_raw)
        close_price = float(price_data.get("close", 0))
        if close_price <= 0:
            return "skipped"

        # ── Fetch cached S/R levels ───────────────────────────────────────────
        sr_key = f"sr_levels:{instrument}"
        sr_raw = r.get(sr_key)
        sr_levels: list[float] = json.loads(sr_raw) if sr_raw else []

        # ── Compute signal ────────────────────────────────────────────────────
        direction = config.get("direction", "long")
        capital_allocated = float(config.get("capital_allocated", 100_000))

        signal = compute_signal(
            instrument=instrument,
            direction=direction,
            entry_price=close_price,
            sr_levels=sr_levels,
            capital_allocated=capital_allocated,
            quantity=int(config.get("lot_size", 1)),
            min_rr_ratio=float(config.get("min_rr_ratio", 2.0)),
        )

        if signal is None:
            return "skipped"

        logger.info(
            "Signal generated: strategy=%s instrument=%s dir=%s entry=%.4f sl=%.4f target=%.4f rr=%.2f",
            strategy_id, signal.instrument, signal.direction,
            signal.entry, signal.stop_loss, signal.target, signal.rr_ratio,
        )

        # ── Semi-auto: just store signal, don't execute ───────────────────────
        if config.get("automation_mode", "semi_auto") == "semi_auto":
            r.setex(
                f"pending_signal:{strategy_id}",
                300,  # expires in 5 min if not approved
                json.dumps({
                    "instrument": signal.instrument,
                    "direction": signal.direction,
                    "entry": signal.entry,
                    "stop_loss": signal.stop_loss,
                    "target": signal.target,
                    "rr_ratio": signal.rr_ratio,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }),
            )
            # Push WebSocket notification for approval
            await async_r.publish(f"ws:{user_id}", json.dumps({
                "channel": "signal",
                "data": json.dumps({
                    "strategy_id": strategy_id,
                    "instrument": signal.instrument,
                    "rr_ratio": signal.rr_ratio,
                    "direction": signal.direction,
                }),
            }))
            return "signal"

        # ── Auto mode: size and execute ───────────────────────────────────────
        # Fetch wallet balance from cache
        wallet_key = f"wallet:{user_id}:{wallet_type}"
        wallet_raw = r.get(wallet_key)
        portfolio_value = float(json.loads(wallet_raw).get("balance", 100_000)) if wallet_raw else 100_000.0

        win_rate = float(config.get("historical_win_rate", 0.5))
        avg_win = float(config.get("avg_win", signal.risk_per_unit * signal.rr_ratio))
        avg_loss = float(config.get("avg_loss", signal.risk_per_unit))

        sizer = KellySizer(
            max_single_trade_pct=settings.max_single_trade_pct,
            max_instrument_pct=settings.max_instrument_pct,
        )
        req = PositionSizeRequest(
            portfolio_value=portfolio_value,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            current_instrument_exposure=0.0,
            method=sizing_method,
        )
        lot_size = sizer.get_position_size(req)

        if lot_size <= 0:
            logger.info("Position size 0 — skipping execution for strategy %s", strategy_id)
            return "skipped"

        # ── Paper trade execution ─────────────────────────────────────────────
        if wallet_type == "paper":
            paper_wallet = PaperWallet(
                user_id=user_id,
                initial_balance=portfolio_value,
                balance=portfolio_value,
            )
            engine_pt = PaperTradingEngine(
                wallet=paper_wallet,
                slippage_pct=float(config.get("slippage_pct", 0.0005)),
                commission_pct=float(config.get("commission_pct", 0.0005)),
            )
            order = engine_pt.submit_market_order(
                instrument=signal.instrument,
                direction=signal.direction,
                quantity=int(lot_size),
                current_price=signal.entry,
            )
            if order.status != "filled":
                logger.warning("Paper order rejected for strategy %s: %s", strategy_id, order.status)
                return "skipped"

            # Persist trade to DB
            db_engine = create_async_engine(settings.database_url, echo=False)
            async with AsyncSession(db_engine) as session:
                trade = Trade(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID(user_id),
                    strategy_id=uuid.UUID(strategy_id),
                    instrument=signal.instrument,
                    direction=signal.direction,
                    entry_price=Decimal(str(order.fill_price)),
                    target=Decimal(str(signal.target)),
                    stop_loss=Decimal(str(signal.stop_loss)),
                    quantity=int(lot_size),
                    status="open",
                    wallet_type=wallet_type,
                    opened_at=datetime.now(timezone.utc),
                )
                session.add(trade)
                await session.commit()
            await db_engine.dispose()

            # Push WebSocket notification
            await async_r.publish(f"ws:{user_id}", json.dumps({
                "channel": "trade_opened",
                "data": json.dumps({
                    "strategy_id": strategy_id,
                    "instrument": signal.instrument,
                    "direction": signal.direction,
                    "entry": float(order.fill_price or signal.entry),
                    "quantity": int(lot_size),
                }),
            }))
            logger.info(
                "Paper trade opened: strategy=%s instrument=%s qty=%d fill=%.4f",
                strategy_id, signal.instrument, int(lot_size), order.fill_price or signal.entry,
            )
            return "trade"

        # Live trading is handled by the broker adapter
        # (requires access_token to be set per user session)
        logger.info(
            "Live trading signal for strategy=%s — broker execution requires active session token",
            strategy_id,
        )
        return "signal"

    finally:
        await async_r.aclose()


@app.task(name="app.workers.strategy_worker.stop_strategy")
def stop_strategy(strategy_id: str, user_id: str) -> None:
    """Publish a stop signal to the strategy worker via Redis."""
    import redis
    from app.core.config import get_settings

    settings = get_settings()
    r = redis.from_url(settings.redis_url)
    r.publish(f"kill:{user_id}", f"stop:{strategy_id}")
    r.close()
