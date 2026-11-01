"""Reuse the webhook client fixtures."""

from tests.webhooks.conftest import client, enqueuer

__all__ = ["client", "enqueuer"]
