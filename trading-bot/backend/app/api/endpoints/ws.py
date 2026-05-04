"""WebSocket endpoint — real-time signals, alerts, and kill switch events."""
from __future__ import annotations
import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings

router = APIRouter(tags=["websocket"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    """
    Per-user WebSocket connection. Subscribes to:
      - signals:{user_id}       — new trade signals
      - alerts:{user_id}        — SL hits, target reached, circuit breaker events
      - kill:{user_id}          — kill switch confirmations
    """
    await websocket.accept()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(
        f"signals:{user_id}",
        f"alerts:{user_id}",
        f"kill:{user_id}",
    )

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(json.dumps({
                    "channel": message["channel"],
                    "data": message["data"],
                }))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user_id=%s", user_id)
    except Exception as e:
        logger.error("WebSocket error for user %s: %s", user_id, e)
    finally:
        await pubsub.unsubscribe()
        await redis.aclose()
