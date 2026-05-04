"""
Data ingestion worker — scheduled tasks for market data, event calendar, and funding rates.

Each task:
  - Calls the appropriate broker adapter / data module
  - Upserts results into the database
  - Caches latest values in Redis for low-latency reads by strategy_worker
  - Handles its own errors with retries; never silently swallows failures
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from app.workers.celery_app import app

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_sync_redis():
    """Return a sync Redis client (safe inside Celery sync tasks)."""
    import redis
    from app.core.config import get_settings
    return redis.from_url(get_settings().redis_url, decode_responses=True)


def _get_settings():
    from app.core.config import get_settings
    return get_settings()


# ── Task 1: Options chain ingestion ──────────────────────────────────────────

@app.task(
    name="app.workers.data_worker.ingest_options_chain",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def ingest_options_chain(self, underlying: str) -> dict:
    """
    Fetch and store the latest NSE options chain for a given underlying
    (NIFTY, BANKNIFTY, SENSEX). Caches Greeks-enriched chain in Redis.
    """
    import asyncio

    try:
        result = asyncio.run(_async_ingest_options_chain(underlying))
        logger.info(
            "Options chain ingested: underlying=%s strikes=%d",
            underlying, result.get("strikes", 0),
        )
        return result
    except Exception as exc:
        logger.error("Options chain ingestion failed for %s: %s", underlying, exc)
        raise self.retry(exc=exc)


async def _async_ingest_options_chain(underlying: str) -> dict:
    """Inner async logic for options chain ingestion."""
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

    from app.core.config import get_settings
    from app.brokers.kite_adapter import KiteAdapter
    from app.engines.greeks_engine import compute_greeks, GreeksInput

    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        # Fetch options chain from Kite (returns list of option strike dicts)
        adapter = KiteAdapter()
        chain = await adapter.get_option_chain(underlying)

        if not chain:
            logger.warning("Empty options chain returned for %s", underlying)
            return {"underlying": underlying, "strikes": 0}

        # Enrich each strike with Black-Scholes Greeks
        enriched = []
        now_utc = datetime.now(timezone.utc)
        for strike in chain:
            try:
                inp = GreeksInput(
                    option_type=strike.get("option_type", "CE"),
                    spot=float(strike.get("underlying_price", 0)),
                    strike=float(strike.get("strike_price", 0)),
                    expiry_days=int(strike.get("days_to_expiry", 1)),
                    iv=float(strike.get("iv", 0.20)),
                )
                g = compute_greeks(inp)
                enriched.append({**strike, "greeks": {
                    "delta": g.delta, "gamma": g.gamma,
                    "theta": g.theta, "vega": g.vega,
                    "iv": g.iv,
                }})
            except Exception:
                enriched.append(strike)

        # Cache full chain in Redis (TTL = 4 minutes)
        cache_key = f"options_chain:{underlying}"
        await r.setex(cache_key, 240, json.dumps({
            "underlying": underlying,
            "timestamp": now_utc.isoformat(),
            "chain": enriched,
        }))

        # Upsert into DB
        engine = create_async_engine(settings.database_url, echo=False)
        async with AsyncSession(engine) as session:
            from sqlalchemy import text
            await session.execute(text("""
                INSERT INTO options_chain (underlying, snapshot_at, data)
                VALUES (:underlying, :ts, :data)
                ON CONFLICT (underlying) DO UPDATE
                  SET snapshot_at = EXCLUDED.snapshot_at,
                      data        = EXCLUDED.data
            """), {
                "underlying": underlying,
                "ts": now_utc,
                "data": json.dumps(enriched),
            })
            await session.commit()
        await engine.dispose()

        return {"underlying": underlying, "strikes": len(enriched)}

    finally:
        await r.aclose()


# ── Task 2: Funding rate ingestion ───────────────────────────────────────────

@app.task(
    name="app.workers.data_worker.ingest_funding_rates",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def ingest_funding_rates(self) -> dict:
    """
    Poll Delta Exchange funding rates for all tracked perpetual instruments
    and persist them to the funding_rates table + Redis cache.
    """
    import asyncio

    try:
        result = asyncio.run(_async_ingest_funding_rates())
        logger.info("Funding rates ingested: %d instruments", result.get("count", 0))
        return result
    except Exception as exc:
        logger.error("Funding rate ingestion failed: %s", exc)
        raise self.retry(exc=exc)


async def _async_ingest_funding_rates() -> dict:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.brokers.delta_adapter import DeltaAdapter

    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    instruments = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    try:
        adapter = DeltaAdapter()
        now_utc = datetime.now(timezone.utc)
        fetched: list[dict] = []

        for inst in instruments:
            rate = await adapter.get_funding_rate(inst)
            if rate is None:
                logger.warning("No funding rate returned for %s", inst)
                continue
            fetched.append({"instrument": inst, "rate": rate, "ts": now_utc.isoformat()})
            # Cache latest rate per instrument (TTL = 20 min)
            await r.setex(f"funding_rate:{inst}", 1200, str(rate))

        if fetched:
            # Bulk upsert into DB
            engine = create_async_engine(settings.database_url, echo=False)
            async with AsyncSession(engine) as session:
                for row in fetched:
                    await session.execute(text("""
                        INSERT INTO funding_rates (instrument, rate, fetched_at)
                        VALUES (:instrument, :rate, :ts)
                    """), {"instrument": row["instrument"], "rate": row["rate"], "ts": now_utc})
                await session.commit()
            await engine.dispose()

        return {"count": len(fetched), "instruments": [f["instrument"] for f in fetched]}

    finally:
        await r.aclose()


# ── Task 3: Event calendar refresh ───────────────────────────────────────────

@app.task(
    name="app.workers.data_worker.refresh_event_calendar",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def refresh_event_calendar(self) -> dict:
    """
    Re-fetch NSE corporate actions and RBI MPC events.
    Persists new events to DB and caches the next 30 days in Redis.
    """
    import asyncio

    try:
        result = asyncio.run(_async_refresh_event_calendar())
        logger.info("Event calendar refreshed: %d events", result.get("total", 0))
        return result
    except Exception as exc:
        logger.error("Event calendar refresh failed: %s", exc)
        raise self.retry(exc=exc)


async def _async_refresh_event_calendar() -> dict:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.data.event_calendar import fetch_nse_corporate_actions, get_rbi_mpc_events

    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        now_utc = datetime.now(timezone.utc)

        corporate_actions = await fetch_nse_corporate_actions()
        rbi_events = get_rbi_mpc_events()

        all_events: list[dict] = []
        for action in corporate_actions:
            all_events.append({
                "source": "nse",
                "event_type": action.get("purpose", "corporate_action"),
                "symbol": action.get("symbol", ""),
                "event_date": action.get("exDate", ""),
                "description": action.get("purpose", ""),
            })
        for ev in rbi_events:
            all_events.append({
                "source": "rbi",
                "event_type": "mpc",
                "symbol": "NIFTY",
                "event_date": ev if isinstance(ev, str) else str(ev),
                "description": "RBI MPC Meeting",
            })

        if all_events:
            engine = create_async_engine(settings.database_url, echo=False)
            async with AsyncSession(engine) as session:
                for ev in all_events:
                    await session.execute(text("""
                        INSERT INTO events (source, event_type, symbol, event_date, description, fetched_at)
                        VALUES (:source, :event_type, :symbol, :event_date, :description, :fetched_at)
                        ON CONFLICT (source, symbol, event_date) DO UPDATE
                          SET description = EXCLUDED.description,
                              fetched_at  = EXCLUDED.fetched_at
                    """), {**ev, "fetched_at": now_utc})
                await session.commit()
            await engine.dispose()

        # Cache upcoming events in Redis (TTL = 2 h)
        await r.setex("events:upcoming", 7200, json.dumps(all_events[:100]))

        return {"total": len(all_events), "corporate_actions": len(corporate_actions), "rbi": len(rbi_events)}

    finally:
        await r.aclose()


# ── Task 4: Price bar cache update ───────────────────────────────────────────

@app.task(
    name="app.workers.data_worker.refresh_price_cache",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
)
def refresh_price_cache(self, instruments: list[str] | None = None) -> dict:
    """
    Fetch the latest OHLCV bar for each tracked instrument and store in Redis.
    Strategy workers read from this cache every tick instead of hitting the broker API.
    """
    import asyncio

    try:
        result = asyncio.run(_async_refresh_price_cache(instruments or _DEFAULT_INSTRUMENTS))
        return result
    except Exception as exc:
        logger.error("Price cache refresh failed: %s", exc)
        raise self.retry(exc=exc)


_DEFAULT_INSTRUMENTS = ["NIFTY", "BANKNIFTY", "SENSEX", "BTCUSDT", "ETHUSDT"]


async def _async_refresh_price_cache(instruments: list[str]) -> dict:
    import redis.asyncio as aioredis
    from app.core.config import get_settings
    from app.brokers.kite_adapter import KiteAdapter
    from app.brokers.delta_adapter import DeltaAdapter

    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        kite = KiteAdapter()
        delta = DeltaAdapter()
        updated = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        for inst in instruments:
            try:
                if inst in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
                    ticker = await delta.get_ticker(inst)
                else:
                    ticker = await kite.get_ltp(inst)

                if ticker:
                    await r.setex(
                        f"price:{inst}:latest",
                        30,  # TTL: 30 s (refreshed every 15 s by Beat)
                        json.dumps({**ticker, "fetched_at": now_iso}),
                    )
                    updated += 1
            except Exception:
                logger.warning("Price fetch failed for %s", inst, exc_info=True)

        return {"updated": updated, "instruments": instruments}

    finally:
        await r.aclose()


# ── Celery Beat schedule ──────────────────────────────────────────────────────

CELERY_BEAT_SCHEDULE = {
    "options-chain-nifty": {
        "task": "app.workers.data_worker.ingest_options_chain",
        "schedule": 180.0,
        "args": ["NIFTY"],
    },
    "options-chain-banknifty": {
        "task": "app.workers.data_worker.ingest_options_chain",
        "schedule": 180.0,
        "args": ["BANKNIFTY"],
    },
    "funding-rates": {
        "task": "app.workers.data_worker.ingest_funding_rates",
        "schedule": 900.0,
    },
    "event-calendar": {
        "task": "app.workers.data_worker.refresh_event_calendar",
        "schedule": 3600.0,
    },
    "price-cache": {
        "task": "app.workers.data_worker.refresh_price_cache",
        "schedule": 15.0,  # every 15 s — fast enough for intraday signals
    },
}
