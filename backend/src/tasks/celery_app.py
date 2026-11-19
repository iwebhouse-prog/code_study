"""Celery app: Redis broker/result backend, queues and shared task settings.

Run a worker with: celery -A src.tasks.celery_app worker --loglevel=info
(on Windows add --pool=solo; the default prefork pool does not work there)
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from celery import Celery
from kombu import Exchange, Queue

from src.config import load_env

REDIS_URL_PATTERN = re.compile(r"rediss?://.+")

# Constitution III: one queue per kind of work so slow AI jobs never block
# quick ones. Task modules are routed by name below.
QUEUES = ("default", "document_generation", "practice_generation", "cleanup")
TASK_ROUTES = {
    "src.tasks.document_generation.*": {"queue": "document_generation"},
    "src.tasks.practice_generation.*": {"queue": "practice_generation"},
    "src.tasks.trash_cleanup.*": {"queue": "cleanup"},
}
# Modules holding @app.task functions; add each one as it is built
# (document_generation T094, practice_generation T118, trash_cleanup T172).
TASK_MODULES: list[str] = ["src.tasks.document_generation"]

TASK_TIME_LIMIT_SECONDS = 300  # Constitution V: task timeout 300 seconds
TASK_SOFT_TIME_LIMIT_SECONDS = 270
# Redis re-sends a task nobody acknowledged after this long. It must outlast
# the slowest task, or a still-running task would be started a second time.
VISIBILITY_TIMEOUT_SECONDS = 3600
RESULT_EXPIRES_SECONDS = 86400


@dataclass(frozen=True)
class CeleryConfig:
    redis_url: str = "redis://127.0.0.1:6379/0"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CeleryConfig":
        env = load_env(env)
        redis_url = env.get("REDIS_URL", cls.redis_url)
        if not REDIS_URL_PATTERN.fullmatch(redis_url):
            raise ValueError(
                "REDIS_URL must look like redis://127.0.0.1:6379/0, "
                f"got {redis_url!r}"
            )
        return cls(redis_url=redis_url)


def create_celery_app(config: CeleryConfig) -> Celery:
    app = Celery("code_study", include=TASK_MODULES)
    app.conf.update(
        broker_url=config.redis_url,
        result_backend=config.redis_url,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"visibility_timeout": VISIBILITY_TIMEOUT_SECONDS},
        # Each queue gets its own exchange and routing key; otherwise all four
        # bind to "default" and the worker banner shows them sharing one key.
        task_queues=[Queue(name, Exchange(name), routing_key=name) for name in QUEUES],
        task_default_queue="default",
        task_routes=TASK_ROUTES,
        task_time_limit=TASK_TIME_LIMIT_SECONDS,
        task_soft_time_limit=TASK_SOFT_TIME_LIMIT_SECONDS,
        # Acknowledge only after the task finishes, so a crashed worker's task
        # is re-run. Tasks must therefore be safe to run twice (idempotent).
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,  # long AI jobs: take one at a time
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        result_expires=RESULT_EXPIRES_SECONDS,
        enable_utc=True,
        timezone="UTC",
    )

    @app.task(name="system.ping")
    def ping() -> str:
        """Lets health checks and tests confirm a worker is consuming tasks."""
        return "pong"

    return app


app = create_celery_app(CeleryConfig.from_env())
