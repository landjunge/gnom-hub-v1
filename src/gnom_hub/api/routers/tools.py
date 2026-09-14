"""HTTP routes: tools."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from gnom_hub.api.models import ActionClickBody, ActionTypeBody, ShellBody, ToolCallBody
from gnom_hub.core.errors import classify_tool_exception, envelope_http
from gnom_hub.hub import get_hub
from gnom_hub.plugins.mcp_protocol import jsonrpc_dispatch
from gnom_hub.plugins.mcp_protocol import tools_call as mcp_tools_call
from gnom_hub.plugins.retry import ToolFailed

router = APIRouter()


@router.post("/api/computer-use/inspect")
def computer_inspect() -> dict[str, Any]:
    """Inspect/OCR requires God-Mode (screen content is sensitive)."""
    hub = get_hub()
    if not hub.god_mode.enabled:
        # Keep kit gate as source of truth; ensure flag is synced
        hub.computer.set_god_mode(False)
    return hub.computer.inspect_screen()


@router.post("/api/computer-use/click")
def computer_click(body: ActionClickBody) -> dict[str, Any]:
    r = get_hub().computer.action.click(body.x, body.y)
    return {"ok": r.ok, "dry_run": r.dry_run, "detail": r.detail}


@router.post("/api/computer-use/type")
def computer_type(body: ActionTypeBody) -> dict[str, Any]:
    r = get_hub().computer.action.type_text(body.text)
    return {"ok": r.ok, "dry_run": r.dry_run, "detail": r.detail}


@router.get("/api/computer-use")
def computer_status() -> dict[str, Any]:
    hub = get_hub()
    return {
        "computer": hub.computer.snapshot(),
        "god_mode": hub.god_mode.snapshot(),
    }


@router.post("/api/computer-use/shell")
def computer_shell(body: ShellBody) -> dict[str, Any]:
    r = get_hub().computer.action.run_shell(body.cmd)
    return {
        "ok": r.ok,
        "dry_run": r.dry_run,
        "detail": r.detail,
        "stdout": r.stdout,
        "stderr": r.stderr,
    }


@router.get("/api/plugins")
def plugins() -> dict[str, Any]:
    hub = get_hub()
    errs = getattr(hub.plugins, "errors", None) or []
    disk = []
    if hasattr(hub.plugins, "scan_disk"):
        try:
            disk = hub.plugins.scan_disk()
        except Exception:  # noqa: BLE001
            disk = []
    return {
        "plugins": hub.plugin_list,
        "disk": disk,
        "tools": hub.tools.list_tools(),
        "errors": errs,
    }


@router.post("/api/plugins/reload")
def plugins_reload(plugin_id: str = "") -> dict[str, Any]:
    """Hot-reload plugins. Optional ?plugin_id= for single plugin; else full scan."""
    hub = get_hub()
    pid = (plugin_id or "").strip()
    if pid:
        result = hub.plugins.reload(pid)
        hub.plugin_list = list(hub.plugins.loaded)
        if isinstance(result, dict) and hasattr(hub.plugins, "scan_disk"):
            result = dict(result)
            result["disk"] = hub.plugins.scan_disk()
            result["tools"] = hub.tools.list_tools()
        return result
    if hasattr(hub, "reload_plugins"):
        out = hub.reload_plugins()
        if isinstance(out, dict) and hasattr(hub.plugins, "scan_disk"):
            out = dict(out)
            out["disk"] = hub.plugins.scan_disk()
        return out
    # fallback: reload registry scan
    result = hub.plugins.reload_all() if hasattr(hub.plugins, "reload_all") else {"ok": False}
    hub.plugin_list = list(getattr(hub.plugins, "loaded", []) or [])
    if isinstance(result, dict):
        result = dict(result)
        result["plugins"] = hub.plugin_list
        result["tools"] = hub.tools.list_tools()
        if hasattr(hub.plugins, "scan_disk"):
            result["disk"] = hub.plugins.scan_disk()
        return result
    return {"ok": True, "plugins": hub.plugin_list}


@router.get("/api/mcp/tools")
def mcp_tools() -> dict[str, Any]:
    """MCP tools/list body (MCP-lite discovery)."""
    return get_hub().tools.mcp_manifest()


@router.post("/api/mcp")
def mcp_jsonrpc(body: dict[str, Any]) -> dict[str, Any]:
    """Minimal JSON-RPC 2.0 surface: tools/list, tools/call, initialize, ping."""
    return jsonrpc_dispatch(get_hub().tools, body if isinstance(body, dict) else {})


@router.post("/api/mcp/call")
def mcp_call(body: ToolCallBody) -> dict[str, Any]:
    """MCP tools/call-shaped response (content[] + isError)."""
    return mcp_tools_call(get_hub().tools, body.name, body.arguments)


@router.post("/api/tools/call")
def tools_call(body: ToolCallBody) -> dict[str, Any]:
    try:
        result = get_hub().tools.call(body.name, body.arguments)
    except (KeyError, ToolFailed) as e:
        env = classify_tool_exception(e, tool_name=body.name or "tool")
        status, detail = envelope_http(env)
        raise HTTPException(status_code=status, detail=detail) from e
    except Exception as e:
        env = classify_tool_exception(e, tool_name=body.name or "tool")
        status, detail = envelope_http(env)
        raise HTTPException(status_code=status, detail=detail) from e
    # Normalize dict results that already say ok:false
    if isinstance(result, dict) and result.get("ok") is False:
        return {
            "ok": False,
            "result": result,
            "error": classify_tool_exception(
                ToolFailed(str(result.get("error") or "tool failed")),
                tool_name=body.name or "tool",
            ),
        }
    return {"ok": True, "result": result}
