"""Prefetch tools for worker stage — URLs + memory_search (KISS, budget-capped)."""

from __future__ import annotations

import re
from typing import Any

_URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+")

# When to auto memory_search (lexical vector)
_MEMORY_HINTS = (
    "memory",
    "erinner",
    "merke",
    "wish",
    "wunsch",
    "prefer",
    "präfer",
    "dark theme",
    "immer",
    "always",
    "flex",
    "warm",
)


def _emit_tool_call(bus: Any, name: str, args: dict[str, Any], result: Any) -> None:
    if bus is None:
        return
    ok = True
    err = None
    summary: Any
    if isinstance(result, dict):
        ok = bool(result.get("ok", True))
        err = result.get("error")
        # keep trace small
        summary = {k: result[k] for k in ("ok", "error", "url", "status") if k in result}
        if "text" in result:
            summary["text_len"] = len(str(result.get("text") or ""))
        if not summary and result:
            summary = {"keys": list(result.keys())[:8]}
    elif isinstance(result, list):
        summary = {"hits": len(result)}
        ok = True
    else:
        summary = {"type": type(result).__name__}
    bus.emit(
        "pipeline.tool_call",
        {
            "name": name,
            "args": {
                k: (str(v)[:120] if not isinstance(v, (int, float, bool)) else v)
                for k, v in (args or {}).items()
            },
            "ok": ok,
            "error": err,
            "result": summary,
        },
    )


def _call_tool(
    tools: Any | None,
    name: str,
    arguments: dict[str, Any],
    *,
    fallback: Any = None,
) -> Any:
    if tools is not None and hasattr(tools, "call"):
        try:
            return tools.call(name, arguments)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "tool": name}
    if callable(fallback):
        return fallback(**arguments)
    return {"ok": False, "error": f"tool {name!r} unavailable"}


def prefetch_for_workers(
    blob: str,
    *,
    bus: Any = None,
    tools: Any | None = None,
    memory: Any | None = None,
    max_tool_calls: int = 5,
    max_urls: int = 3,
) -> str:
    """
    Run allowlisted prefetches and return a context block for workers.

    - http(s) URLs → web_fetch (via ToolRegistry when present)
    - memory_search when hints match and vectors available
    Emits pipeline.tool_call per invocation. Caps at max_tool_calls.
    """
    text = blob or ""
    chunks: list[str] = []
    calls = 0

    # ── URLs ──────────────────────────────────────────────────────────
    urls: list[str] = []
    seen: set[str] = set()
    for raw in _URL_RE.findall(text):
        u = raw.rstrip(".,;:)")
        if u in seen:
            continue
        seen.add(u)
        urls.append(u)
        if len(urls) >= max_urls:
            break

    for u in urls:
        if calls >= max_tool_calls:
            break
        from gnom_hub.tools.web_fetch import web_fetch

        args = {"url": u, "max_chars": 2500}
        res = _call_tool(
            tools,
            "web_fetch",
            args,
            fallback=lambda url, max_chars=2500: web_fetch(str(url), max_chars=int(max_chars)),
        )
        calls += 1
        _emit_tool_call(bus, "web_fetch", args, res)
        if isinstance(res, dict) and res.get("ok"):
            chunks.append(f"URL: {res.get('url') or u}\n{str(res.get('text') or '')[:2500]}")
        else:
            err = res.get("error") if isinstance(res, dict) else "fetch failed"
            chunks.append(f"URL: {u}\n(fetch failed: {err})")

    # ── memory_search ─────────────────────────────────────────────────
    low = text.lower()
    want_mem = any(h in low for h in _MEMORY_HINTS)
    vectors = getattr(memory, "vectors", None) if memory is not None else None
    if want_mem and vectors is not None and calls < max_tool_calls:
        # Prefer first user-looking line / head of blob as query
        query = " ".join(text.split())[:180]
        args = {"query": query, "limit": 3}
        if tools is not None and hasattr(tools, "call"):
            try:
                hits = tools.call("memory_search", args)
            except Exception as exc:  # noqa: BLE001
                hits = {"ok": False, "error": str(exc)}
        else:
            try:
                hits = vectors.search(query, limit=3)
            except Exception as exc:  # noqa: BLE001
                hits = {"ok": False, "error": str(exc)}
        calls += 1
        _emit_tool_call(bus, "memory_search", args, hits)
        if isinstance(hits, list) and hits:
            lines = []
            for h in hits[:3]:
                if isinstance(h, dict):
                    lines.append(f"- ({h.get('score', '?')}) {str(h.get('text') or '')[:160]}")
            if lines:
                chunks.append("Memory search (auto):\n" + "\n".join(lines))
        elif isinstance(hits, dict) and hits.get("error"):
            chunks.append(f"Memory search failed: {hits.get('error')}")

    if not chunks:
        return ""
    return "\n---\n".join(chunks)


def tool_calls_needed(blob: str) -> list[str]:
    """Which tools would prefetch attempt (for tests / planning)."""
    text = blob or ""
    out: list[str] = []
    if _URL_RE.search(text):
        out.append("web_fetch")
    low = text.lower()
    if any(h in low for h in _MEMORY_HINTS):
        out.append("memory_search")
    return out
