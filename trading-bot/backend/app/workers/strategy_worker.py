"""
Live strategy worker — runs one Celery task per active strategy.
Subscribes to the Redis kill channel to stop immediately on Kill Switch.
"""
from __future__ import annotations
import asyncio
import logging

from app.workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, name="app.workers.strategy_worker.run_strategy", max_retries=3)
def run_strategy(self, strategy_id: str, user_id: str) -> dict:
    """
    Long-running strategy execution task.
    Subscribes to kill:{user_id} Redis channel; stops on kill signal.
    Returns summary dict on completion.
    """
    import redis
    from app.core.config import get_settings

    settings = get_settings()
    r = redis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    pubsub.subscribe(f"kill:{user_id}")

    logger.info("Strategy worker started: strategy_id=%s user_id=%s", strategy_id, user_id)

    try:
        # Main strategy loop (simplified — production loop hooks into live data feed)
        while True:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message and message.get("type") == "message":
                data = message.get("data", b"").decode()
                logger.warning(
                    "Kill signal received for user=%s payload=%s — stopping strategy %s",
                    user_id, data, strategy_id,
                )
                pubsub.unsubscribe()
                return {"status": "killed", "strategy_id": strategy_id}

            # Signal generation would happen here in production:
            # signal = await signal_engine.compute_signal(...)
            # Placeholder: yield to avoid CPU spin
            import time
            time.sleep(1)

    except Exception as exc:
        logger.exception("Strategy worker error: strategy_id=%s", strategy_id)
        raise self.retry(exc=exc, countdown=5)
    finally:
        pubsub.close()
        r.close()


@app.task(name="app.workers.strategy_worker.stop_strategy")
def stop_strategy(strategy_id: str, user_id: str) -> None:
    """Publish a stop signal to the strategy worker via Redis."""
    import redis
    from app.core.config import get_settings

    settings = get_settings()
    r = redis.from_url(settings.redis_url)
    r.publish(f"kill:{user_id}", f"stop:{strategy_id}")
    r.close()
