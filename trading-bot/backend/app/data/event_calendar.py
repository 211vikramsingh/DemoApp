"""
Event calendar data ingestion.
Fetches NSE corporate actions, RBI MPC dates, and economic events.
Stores in the `events` table. Blackout filter prevents signal generation
within 30 minutes of a high-impact event.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

BLACKOUT_WINDOW_MINUTES = 30


async def is_event_blackout(
    db_session,
    instrument: str | None,
    check_time: datetime | None = None,
) -> tuple[bool, str]:
    """
    Check if there is a high-impact event within the blackout window.
    Returns (is_blacked_out, event_title).
    """
    from sqlalchemy import select, or_
    from app.models.audit_log import MarketEvent

    now = check_time or datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=BLACKOUT_WINDOW_MINUTES)
    window_end = now + timedelta(minutes=BLACKOUT_WINDOW_MINUTES)

    stmt = select(MarketEvent).where(
        MarketEvent.impact == "high",
        MarketEvent.scheduled_at.between(window_start, window_end),
        or_(MarketEvent.instrument == instrument, MarketEvent.instrument.is_(None)),
    )
    result = await db_session.execute(stmt)
    event = result.scalars().first()
    if event:
        return True, event.title
    return False, ""


async def fetch_nse_corporate_actions() -> list[dict]:
    """
    Fetch NSE corporate actions (earnings, dividends, splits).
    Returns list of event dicts ready for DB insertion.
    """
    url = "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com",
    }
    events = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("data", []):
                events.append({
                    "title": f"{item.get('symbol', '')} — {item.get('subject', '')}",
                    "event_type": "earnings",
                    "impact": "high",
                    "instrument": item.get("symbol"),
                    "scheduled_at": item.get("exDate"),
                })
    except Exception as e:
        logger.warning("Failed to fetch NSE corporate actions: %s", e)
    return events


# RBI MPC dates are manually maintained or scraped from RBI press releases.
RBI_MPC_DATES_2025_2026 = [
    "2025-06-06", "2025-08-08", "2025-10-08", "2025-12-05",
    "2026-02-07", "2026-04-09",
]


def get_rbi_mpc_events() -> list[dict]:
    return [
        {
            "title": "RBI MPC Policy Decision",
            "event_type": "rbi_mpc",
            "impact": "high",
            "instrument": None,
            "scheduled_at": f"{d}T10:00:00+05:30",
        }
        for d in RBI_MPC_DATES_2025_2026
    ]
