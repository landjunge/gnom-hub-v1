"""Pipeline constants and cancel signal."""

from __future__ import annotations

ALLOWED_SEND_TARGETS = frozenset(
    {
        "brainstorm",
        "coordinator",
        "flex",
        "worker1",
        "worker2",
        "worker3",
        "worker4",
    }
)


class PipelineCancelled(Exception):
    """Raised when cooperative soft-cancel aborts a pipeline mid-run."""
