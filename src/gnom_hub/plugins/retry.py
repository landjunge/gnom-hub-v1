"""Retry shell for ToolRegistry — ModelRetry-style control for agents.

Tools raise ToolRetry to request another attempt with the same args.
Raise ToolFailed for terminal errors (no further retries).

ToolRegistry.call() catches ToolRetry up to ``retries`` times, then
raises ToolFailed. Call sites (API, Telegram, workers) only need to
handle ToolFailed / KeyError.
"""

from __future__ import annotations

from typing import Any


class ToolRetry(Exception):
    """Ask the caller / agent to retry this tool call (counts against budget)."""

    def __init__(self, message: str = "retry tool call") -> None:
        super().__init__(message)
        self.message = message


class ToolFailed(Exception):
    """Terminal tool failure — do not retry the same call.

    Optional structured fields feed ``core.errors`` envelopes / API detail.
    """

    def __init__(
        self,
        message: str = "tool failed",
        *,
        code: str = "tool_failed",
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = bool(retryable)
        self.details = dict(details or {})


def call_with_retry(
    handler: Any,
    arguments: dict[str, Any] | None = None,
    *,
    retries: int = 2,
    tool_name: str = "tool",
) -> Any:
    """Invoke ``handler(**arguments)`` with ToolRetry budget.

    Parameters
    ----------
    handler :
        Callable tool implementation.
    arguments :
        Keyword args for the handler.
    retries :
        Extra attempts after the first (default 2 → up to 3 runs).
    tool_name :
        Used only in exhausted-retry error text.
    """
    args = arguments or {}
    budget = max(0, int(retries))
    attempts = budget + 1
    last_msg = ""

    for attempt in range(attempts):
        try:
            return handler(**args)
        except ToolFailed:
            raise
        except ToolRetry as exc:
            last_msg = (exc.message or str(exc) or "retry").strip()
            if attempt + 1 >= attempts:
                raise ToolFailed(
                    f"tool {tool_name!r} exceeded retries ({budget}): {last_msg}",
                    code="tool_retry_exhausted",
                    retryable=False,
                    details={"attempts": attempts, "tool": tool_name},
                ) from exc
            continue

    raise ToolFailed(
        f"tool {tool_name!r} failed after retries",
        code="tool_retry_exhausted",
        retryable=False,
    )
