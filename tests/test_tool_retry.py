"""Retry shell for ToolRegistry."""

from __future__ import annotations

import pytest

from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.plugins.retry import ToolFailed, ToolRetry, call_with_retry


def test_call_with_retry_succeeds_first_try():
    def ok(x: int = 0) -> int:
        return x + 1

    assert call_with_retry(ok, {"x": 1}, retries=2) == 2


def test_call_with_retry_recovers():
    state = {"n": 0}

    def flaky() -> str:
        state["n"] += 1
        if state["n"] < 3:
            raise ToolRetry(f"attempt {state['n']}")
        return "done"

    assert call_with_retry(flaky, retries=2) == "done"
    assert state["n"] == 3


def test_call_with_retry_exhausted():
    def always() -> None:
        raise ToolRetry("still broken")

    with pytest.raises(ToolFailed) as ei:
        call_with_retry(always, retries=1, tool_name="x")
    assert "exceeded retries" in str(ei.value)
    assert "still broken" in str(ei.value)


def test_tool_failed_no_retry():
    state = {"n": 0}

    def hard() -> None:
        state["n"] += 1
        raise ToolFailed("nope")

    with pytest.raises(ToolFailed, match="nope"):
        call_with_retry(hard, retries=5)
    assert state["n"] == 1


def test_registry_call_retries():
    state = {"n": 0}

    def flaky() -> str:
        state["n"] += 1
        if state["n"] < 2:
            raise ToolRetry("once")
        return "ok"

    reg = ToolRegistry()
    reg.register(ToolSpec(name="flaky", description="t", handler=flaky, retries=2))
    assert reg.call("flaky") == "ok"
    assert state["n"] == 2


def test_registry_call_retries_override():
    state = {"n": 0}

    def always() -> None:
        state["n"] += 1
        raise ToolRetry("x")

    reg = ToolRegistry()
    reg.register(ToolSpec(name="a", description="t", handler=always, retries=5))
    with pytest.raises(ToolFailed):
        reg.call("a", retries=0)
    assert state["n"] == 1
