"""MCP-shaped protocol helpers over the in-process ToolRegistry (MCP-lite).

This is **not** a full Model Context Protocol stdio/SSE server.
It maps Gnom-Hub tools to MCP-like ``tools/list`` + ``tools/call`` payloads so:

* external agents can discover tools via ``GET /api/mcp/tools``
* a future stdio MCP process can reuse the same handlers
* UI / Telegram / pipeline share one registry

Full MCP (JSON-RPC 2.0 over stdio) remains optional — see docs/MCP_ARCHITECTURE.md.
"""

from __future__ import annotations

from typing import Any

from gnom_hub.core.errors import classify_tool_exception, error_envelope
from gnom_hub.plugins.registry import ToolRegistry
from gnom_hub.plugins.retry import ToolFailed


def tools_list(registry: ToolRegistry) -> dict[str, Any]:
    """MCP tools/list result body (without JSON-RPC wrapper)."""
    return registry.mcp_manifest()


def tools_call(
    registry: ToolRegistry,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    MCP tools/call-style result.

    Success::
        {"ok": True, "content": [{"type": "text", "text": "..."}], "isError": False, "result": <raw>}

    Failure::
        {"ok": False, "isError": True, "content": [...], "error": <envelope>}
    """
    nm = (name or "").strip()
    try:
        raw = registry.call(nm, arguments or {})
    except (KeyError, ToolFailed) as exc:
        env = classify_tool_exception(exc, tool_name=nm or "tool")
        return {
            "ok": False,
            "isError": True,
            "content": [{"type": "text", "text": env.get("message") or str(exc)}],
            "error": env,
        }
    except Exception as exc:  # noqa: BLE001
        env = classify_tool_exception(exc, tool_name=nm or "tool")
        return {
            "ok": False,
            "isError": True,
            "content": [{"type": "text", "text": env.get("message") or str(exc)}],
            "error": env,
        }

    if isinstance(raw, dict) and raw.get("ok") is False:
        msg = str(raw.get("error") or "tool failed")
        env = error_envelope(
            message=msg,
            code="tool_failed",
            layer="tool",
            retryable=False,
            extra={"tool": nm},
        )
        return {
            "ok": False,
            "isError": True,
            "content": [{"type": "text", "text": msg}],
            "error": env,
            "result": raw,
        }

    text = raw if isinstance(raw, str) else _to_text(raw)
    return {
        "ok": True,
        "isError": False,
        "content": [{"type": "text", "text": text}],
        "result": raw,
    }


def jsonrpc_dispatch(registry: ToolRegistry, body: dict[str, Any]) -> dict[str, Any]:
    """
    Minimal JSON-RPC 2.0 dispatcher for MCP-like methods.

    Supported methods:
      * ``tools/list``
      * ``tools/call``  params: { name, arguments? }
      * ``initialize``  (capability stub)
      * ``ping``
    """
    req_id = body.get("id")
    method = str(body.get("method") or "").strip()
    params = body.get("params") if isinstance(body.get("params"), dict) else {}

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code: int, message: str, data: Any = None) -> dict[str, Any]:
        e: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }
        if data is not None:
            e["error"]["data"] = data
        return e

    if body.get("jsonrpc") not in (None, "2.0"):
        return err(-32600, "invalid jsonrpc version")

    if method in ("tools/list", "tools.list"):
        return ok(tools_list(registry))

    if method in ("tools/call", "tools.call"):
        name = str(params.get("name") or params.get("tool") or "").strip()
        arguments = params.get("arguments") or params.get("args") or {}
        if not isinstance(arguments, dict):
            return err(-32602, "arguments must be object")
        if not name:
            return err(-32602, "name required")
        out = tools_call(registry, name, arguments)
        if out.get("isError"):
            return err(-32000, out.get("error", {}).get("message") or "tool error", out)
        return ok(out)

    if method == "initialize":
        return ok(
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "gnom-hub-mcp-lite", "version": "3.7"},
            }
        )

    if method in ("ping", "notifications/initialized"):
        return ok({"ok": True})

    return err(-32601, f"method not found: {method}")


def _to_text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, (dict, list)):
        import json

        try:
            return json.dumps(raw, ensure_ascii=False, indent=2)[:12000]
        except (TypeError, ValueError):
            return str(raw)[:12000]
    return str(raw)[:12000]


__all__ = ["jsonrpc_dispatch", "tools_call", "tools_list"]
