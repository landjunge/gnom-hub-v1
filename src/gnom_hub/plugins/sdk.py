"""Small helpers for plugin authors (optional import in main.py)."""

from __future__ import annotations

from typing import Any

from gnom_hub.plugins.retry import ToolFailed, ToolRetry

__all__ = [
    "ToolFailed",
    "ToolRetry",
    "fail",
    "ok",
    "retry",
]


def ok(**fields: Any) -> dict[str, Any]:
    """Standard success payload: ``{"ok": True, ...}``."""
    out: dict[str, Any] = {"ok": True}
    out.update(fields)
    return out


def fail(error: str, *, retryable: bool = False, **fields: Any) -> dict[str, Any]:
    """
    Failure as structured result *or* raise.

    If ``retryable`` is True, raises ``ToolRetry`` so the registry re-attempts.
    Otherwise returns ``{"ok": False, "error": ...}`` (does not raise).
    """
    msg = str(error or "failed")
    if retryable:
        raise ToolRetry(msg)
    out: dict[str, Any] = {"ok": False, "error": msg}
    out.update(fields)
    return out


def retry(message: str) -> None:
    """Raise ``ToolRetry`` (transient)."""
    raise ToolRetry(str(message or "retry"))
