"""MCP-lite protocol over ToolRegistry."""

from __future__ import annotations

from gnom_hub.plugins.mcp_protocol import jsonrpc_dispatch, tools_call, tools_list
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.plugins.retry import ToolFailed


def _reg() -> ToolRegistry:
    r = ToolRegistry()
    r.register(
        ToolSpec(
            name="echo",
            description="echo text",
            handler=lambda text="": {"ok": True, "text": text},
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            plugin="core",
        )
    )
    r.register(
        ToolSpec(
            name="boom",
            description="fail",
            handler=lambda: (_ for _ in ()).throw(ToolFailed("nope", code="tool_failed")),
            retries=0,
            plugin="core",
        )
    )
    return r


def test_tools_list_shape():
    m = tools_list(_reg())
    names = {t["name"] for t in m["tools"]}
    assert "echo" in names
    echo = next(t for t in m["tools"] if t["name"] == "echo")
    assert "inputSchema" in echo
    assert "text" in (echo["inputSchema"].get("properties") or {})


def test_tools_call_success_content():
    out = tools_call(_reg(), "echo", {"text": "hi"})
    assert out["ok"] is True
    assert out["isError"] is False
    assert out["content"][0]["type"] == "text"
    assert "hi" in out["content"][0]["text"] or out["result"]["text"] == "hi"


def test_tools_call_missing_arg():
    out = tools_call(_reg(), "echo", {})
    assert out["isError"] is True
    assert out["error"]["code"] in ("tool_failed", "validation")


def test_tools_call_failed():
    out = tools_call(_reg(), "boom", {})
    assert out["isError"] is True
    assert out["error"]["layer"] == "tool"


def test_jsonrpc_tools_list_and_call():
    reg = _reg()
    listed = jsonrpc_dispatch(reg, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert "result" in listed
    assert any(t["name"] == "echo" for t in listed["result"]["tools"])

    called = jsonrpc_dispatch(
        reg,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"text": "z"}},
        },
    )
    assert "result" in called
    assert called["result"]["ok"] is True

    bad = jsonrpc_dispatch(reg, {"jsonrpc": "2.0", "id": 3, "method": "nope"})
    assert bad["error"]["code"] == -32601


def test_jsonrpc_initialize():
    r = jsonrpc_dispatch(_reg(), {"jsonrpc": "2.0", "id": 0, "method": "initialize"})
    assert r["result"]["serverInfo"]["name"] == "gnom-hub-mcp-lite"
