"""Shared pytest settings."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from src.tasks.document_generation import generate_document


@pytest.fixture(autouse=True)
def no_real_document_queueing() -> Iterator[MagicMock]:
    """An upload queues a Celery task (T096); tests must never reach Redis.

    Tests of the queueing itself patch apply_async again with their own mock.
    """
    with patch.object(generate_document, "apply_async") as apply_async:
        yield apply_async
