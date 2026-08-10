"""Central error envelopes + tool/API mapping."""

from __future__ import annotations

import pytest

from gnom_hub.core.errors import (
    ErrorCode,
    ErrorLayer,
    classify_generic_exception,
    classify_tool_exception,
    envelope_http,
    error_envelope,
    sanitize_message,
)
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.plugins.retry import ToolFailed, ToolRetry, call_with_retry


def test_sanitize_strips_long_sk_tokens():
    s = sanitize_message("bad key sk-abcdefghijklmnopqrstuvwxyz1234 end")
    assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in s
    assert "sk-…" in s


def test_error_envelope_shape():
    env = error_envelope(
        message="x",
        code=ErrorCode.VALIDATION,
        layer=ErrorLayer.VALIDATION,
        retryable=False,
    )
    assert env["ok"] is False
    assert env["code"] == "validation"
    assert env["layer"] == "validation"
    assert env["retryable"] is False


def test_tool_failed_structured_fields():
    exc = ToolFailed("nope", code="validation", retryable=False, details={"a": 1})
    env = classify_tool_exception(exc, tool_name="echo")
    assert env["code"] == "validation"
    assert env["tool"] == "echo"
    status, body = envelope_http(env)
    assert status == 422
    assert body["message"] == "nope"


def test_call_with_retry_exhausted():
    n = {"i": 0}

    def flaky():
        n["i"] += 1
        raise ToolRetry("again")

    with pytest.raises(ToolFailed) as ei:
        call_with_retry(flaky, retries=1, tool_name="flaky")
    assert ei.value.code == "tool_retry_exhausted"
    assert n["i"] == 2


def test_registry_wraps_unexpected_exception():
    reg = ToolRegistry()

    def boom():
        raise RuntimeError("secret sk-abcdefghijklmnopqrstuvwxyz99")

    reg.register(ToolSpec(name="boom", description="x", handler=boom, retries=0))
    with pytest.raises(ToolFailed) as ei:
        reg.call("boom", {})
    assert ei.value.code == "internal"
    env = classify_tool_exception(ei.value, tool_name="boom")
    assert "sk-abcdefghijklmnopqrstuvwxyz99" not in env["message"] or "sk-…" in env["message"]


def test_registry_unknown_tool_keyerror():
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.call("nope", {})
    env = classify_tool_exception(KeyError("Unknown tool: nope"), tool_name="nope")
    assert env["code"] == "tool_unknown"
    assert envelope_http(env)[0] == 404


def test_classify_file_not_found():
    env = classify_generic_exception(FileNotFoundError("missing.zip"))
    assert env["code"] == "not_found_file"
    assert envelope_http(env)[0] == 404
