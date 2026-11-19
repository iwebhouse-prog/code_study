"""Verifies Celery settings, queues and routing (T017)."""

import os
import unittest
from unittest.mock import patch

from src import config as app_config_module
from src.tasks import celery_app as celery_module
from src.tasks.celery_app import (
    QUEUES,
    CeleryConfig,
    create_celery_app,
)

REDIS_URL = "redis://127.0.0.1:6379/0"


class TestCeleryConfigFromEnv(unittest.TestCase):
    def test_reads_redis_url(self) -> None:
        url = "redis://cache:6380/2"
        self.assertEqual(CeleryConfig.from_env({"REDIS_URL": url}).redis_url, url)

    def test_default_matches_docker_compose(self) -> None:
        self.assertEqual(CeleryConfig.from_env({}).redis_url, REDIS_URL)

    def test_tls_redis_url_is_allowed(self) -> None:
        url = "rediss://cache.example.com:6380/0"
        self.assertEqual(CeleryConfig.from_env({"REDIS_URL": url}).redis_url, url)

    def test_non_redis_url_is_rejected(self) -> None:
        for url in ("amqp://guest@localhost//", "127.0.0.1:6379"):
            with (
                self.subTest(url=url),
                self.assertRaisesRegex(ValueError, "REDIS_URL"),
            ):
                CeleryConfig.from_env({"REDIS_URL": url})

    def test_reads_process_environment_by_default(self) -> None:
        url = "redis://from-env:6379/1"
        with (
            patch.object(app_config_module, "load_dotenv"),
            patch.dict(os.environ, {"REDIS_URL": url}),
        ):
            self.assertEqual(CeleryConfig.from_env().redis_url, url)


class TestCreateCeleryApp(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_celery_app(CeleryConfig(redis_url=REDIS_URL))

    def test_redis_is_broker_and_result_backend(self) -> None:
        self.assertEqual(self.app.conf.broker_url, REDIS_URL)
        self.assertEqual(self.app.conf.result_backend, REDIS_URL)

    def test_queues_follow_constitution(self) -> None:
        self.assertEqual(
            QUEUES,
            ("default", "document_generation", "practice_generation", "cleanup"),
        )
        names = [queue.name for queue in self.app.conf.task_queues]
        self.assertEqual(names, list(QUEUES))
        self.assertEqual(self.app.conf.task_default_queue, "default")

    def test_each_queue_has_its_own_routing_key(self) -> None:
        # Queues sharing one routing key would each get a copy of every task.
        for queue in self.app.conf.task_queues:
            with self.subTest(queue=queue.name):
                self.assertEqual(queue.routing_key, queue.name)
                self.assertEqual(queue.exchange.name, queue.name)

    def test_tasks_are_routed_by_module(self) -> None:
        expected = {
            "src.tasks.document_generation.generate": "document_generation",
            "src.tasks.practice_generation.generate": "practice_generation",
            "src.tasks.trash_cleanup.purge": "cleanup",
            "system.ping": "default",
        }
        for task_name, queue in expected.items():
            with self.subTest(task=task_name):
                route = self.app.amqp.router.route({}, task_name)
                self.assertEqual(route["queue"].name, queue)

    def test_time_limit_is_five_minutes(self) -> None:
        # Constitution: Celery task timeout 300 seconds.
        self.assertEqual(self.app.conf.task_time_limit, 300)
        # The soft limit fires first so a task can record "failed" itself.
        self.assertLess(self.app.conf.task_soft_time_limit, 300)

    def test_redelivery_waits_longer_than_any_task(self) -> None:
        # With late acks, Redis re-sends unacknowledged tasks after this timeout;
        # a shorter one would run a slow task twice.
        timeout = self.app.conf.broker_transport_options["visibility_timeout"]
        self.assertGreater(timeout, self.app.conf.task_time_limit)

    def test_unfinished_tasks_survive_worker_crash(self) -> None:
        self.assertTrue(self.app.conf.task_acks_late)
        self.assertTrue(self.app.conf.task_reject_on_worker_lost)
        self.assertEqual(self.app.conf.worker_prefetch_multiplier, 1)

    def test_only_json_is_accepted(self) -> None:
        # pickle would let anyone who can write to Redis run code on workers.
        self.assertEqual(self.app.conf.task_serializer, "json")
        self.assertEqual(self.app.conf.result_serializer, "json")
        self.assertEqual(list(self.app.conf.accept_content), ["json"])

    def test_started_state_is_reported(self) -> None:
        # The status API (T098) shows "in progress" from this state.
        self.assertTrue(self.app.conf.task_track_started)

    def test_results_expire_after_one_day(self) -> None:
        self.assertEqual(self.app.conf.result_expires, 86400)

    def test_ping_task_runs_locally(self) -> None:
        ping = self.app.tasks["system.ping"]
        self.assertEqual(ping.apply().get(), "pong")

    def test_each_call_builds_independent_app(self) -> None:
        other = create_celery_app(CeleryConfig(redis_url="redis://other:6379/0"))
        self.assertIsNot(other, self.app)
        self.assertEqual(self.app.conf.broker_url, REDIS_URL)


class TestModuleApp(unittest.TestCase):
    def test_cli_can_find_app(self) -> None:
        # `celery -A src.tasks.celery_app worker` looks for a module attribute `app`.
        self.assertIn("system.ping", celery_module.app.tasks)
