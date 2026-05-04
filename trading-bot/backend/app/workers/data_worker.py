"""
Data ingestion worker — scheduled tasks for market data, event calendar, and funding rates.
"""
from __future__ import annotations
import logging

from app.workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(name="app.workers.data_worker.ingest_options_chain")
def ingest_options_chain(underlying: str) -> None:
    """Fetch and store latest NSE options chain for given underlying (Nifty, BankNifty)."""
    logger.info("Ingesting options chain for %s", underlying)
    # Production: call KiteAdapter.get_option_chain() and upsert into options_chain table


@app.task(name="app.workers.data_worker.ingest_funding_rates")
def ingest_funding_rates() -> None:
    """Poll Delta Exchange funding rates and store in funding_rates table."""
    import asyncio
    from app.brokers.delta_adapter import DeltaAdapter

    adapter = DeltaAdapter()
    instruments = ["BTCUSDT", "ETHUSDT"]

    async def _poll():
        for inst in instruments:
            rate = await adapter.get_funding_rate(inst)
            if rate is not None:
                logger.info("Funding rate %s: %.6f", inst, rate)
                # Production: store to DB

    asyncio.run(_poll())


@app.task(name="app.workers.data_worker.refresh_event_calendar")
def refresh_event_calendar() -> None:
    """Re-fetch NSE corporate actions and store new events."""
    import asyncio
    from app.data.event_calendar import fetch_nse_corporate_actions, get_rbi_mpc_events

    async def _fetch():
        actions = await fetch_nse_corporate_actions()
        logger.info("Fetched %d NSE corporate action events", len(actions))
        # Production: upsert into events table

    asyncio.run(_fetch())
    logger.info("RBI MPC events: %d pre-loaded", len(get_rbi_mpc_events()))


# ── Celery Beat schedule (add to celery_app.conf if using beat) ───────────────
CELERY_BEAT_SCHEDULE = {
    "options-chain-nifty": {
        "task": "app.workers.data_worker.ingest_options_chain",
        "schedule": 180.0,  # every 3 minutes during market hours
        "args": ["NIFTY"],
    },
    "options-chain-banknifty": {
        "task": "app.workers.data_worker.ingest_options_chain",
        "schedule": 180.0,
        "args": ["BANKNIFTY"],
    },
    "funding-rates": {
        "task": "app.workers.data_worker.ingest_funding_rates",
        "schedule": 900.0,  # every 15 minutes
    },
    "event-calendar": {
        "task": "app.workers.data_worker.refresh_event_calendar",
        "schedule": 3600.0,  # every hour
    },
}
