from celery import Celery
from app.core.config import get_settings

settings = get_settings()

app = Celery(
    "trading_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.strategy_worker",
        "app.workers.data_worker",
    ],
)

app.conf.update(
    task_routes={
        "app.workers.strategy_worker.*": {"queue": "default"},
        "app.workers.data_worker.*": {"queue": "default"},
        # Kill tasks always go to the high-priority kill_queue
        "app.workers.kill_worker.*": {"queue": "kill_queue"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
