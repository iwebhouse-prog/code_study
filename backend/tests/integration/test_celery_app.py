"""Sends a task through real Redis to an in-process worker (T017)."""

import socket
import unittest

import redis
from celery.contrib.testing.worker import start_worker

from src.tasks.celery_app import QUEUES, CeleryConfig, create_celery_app

# A separate Redis database so tests never touch the development queue.
TEST_REDIS_URL = "redis://127.0.0.1:6379/15"


def redis_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 6379), timeout=1):
            return True
    except OSError:
        return False


@unittest.skipUnless(redis_reachable(), "Redis is not running on :6379")
class TestCeleryWithRedis(unittest.TestCase):
    def tearDown(self) -> None:
        redis.Redis.from_url(TEST_REDIS_URL).flushdb()

    def test_ping_round_trip_through_worker(self) -> None:
        app = create_celery_app(CeleryConfig(redis_url=TEST_REDIS_URL))
        with start_worker(
            app, pool="solo", perform_ping_check=False, shutdown_timeout=10
        ):
            result = app.tasks["system.ping"].delay()
            self.assertEqual(result.get(timeout=10), "pong")
        self.assertEqual(result.state, "SUCCESS")

    def test_broker_connection(self) -> None:
        app = create_celery_app(CeleryConfig(redis_url=TEST_REDIS_URL))
        with app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=1)
            self.assertTrue(connection.connected)

    def test_task_lands_only_in_its_own_queue(self) -> None:
        app = create_celery_app(CeleryConfig(redis_url=TEST_REDIS_URL))
        app.tasks["system.ping"].apply_async(queue="document_generation")
        client = redis.Redis.from_url(TEST_REDIS_URL)
        lengths = {name: client.llen(name) for name in QUEUES}
        self.assertEqual(
            lengths,
            {
                "default": 0,
                "document_generation": 1,
                "practice_generation": 0,
                "cleanup": 0,
            },
        )
