"""Prefetch tools for worker stage — URLs + memory + install_tool (KISS, budget-capped)."""

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

# Task keywords → allowlisted install_tool package key
# Keep aligned with plugins/install_tool/main.py _ALLOW
_PACKAGE_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("playwright", ("playwright", "chromium", "browser e2e", "headed browser")),
    ("beautifulsoup4", ("beautifulsoup", "beautifulsoup4", " bs4 ", "bs4.", "html soup")),
    ("lxml", ("lxml",)),
    ("pillow", ("pillow", " PIL", "screenshot png", "image screenshot")),
    ("pytesseract", ("pytesseract", "ocr ", "tesseract")),
    ("pyautogui", ("pyautogui", "mouse click", "gui automation")),
    ("mss", (" mss", "screen capture", "monitor capture")),
    ("pynput", ("pynput", "keyboard control", "mouse control")),
]


def packages_needed(blob: str) -> list[str]:
    """Allowlisted package keys implied by task text (order preserved)."""
    low = f" {(blob or '').lower()} "
    out: list[str] = []
    seen: set[str] = set()
    for pkg, keys in _PACKAGE_HINTS:
        if pkg not in seen and any(k in low for k in keys):
            seen.add(pkg)
            out.append(pkg)
    return out


def _emit_tool_call(
    bus: Any,
    name: str,
    args: dict[str, Any],
    result: Any,
    record: list[dict[str, Any]] | None = None,
) -> None:
    ok = True
    err = None
    summary: Any
    if isinstance(result, dict):
        ok = bool(result.get("ok", True))
        err = result.get("error")
        # keep trace small
        keys = (
            "ok",
            "error",
            "url",
            "status",
            "package",
            "installed",
            "already_installed",
            "message",
            "dry_run",
        )
        summary = {k: result[k] for k in keys if k in result}
        if "text" in result:
            summary["text_len"] = len(str(result.get("text") or ""))
        if not summary and result:
            summary = {"keys": list(result.keys())[:8]}
    elif isinstance(result, list):
        summary = {"hits": len(result)}
        ok = True
    else:
        summary = {"type": type(result).__name__}
    payload = {
        "name": name,
        "args": {
            k: (str(v)[:120] if not isinstance(v, (int, float, bool)) else v)
            for k, v in (args or {}).items()
        },
        "ok": ok,
        "error": err,
        "result": summary,
    }
    if bus is not None:
        bus.emit("pipeline.tool_call", payload)
    if record is not None:
        record.append(dict(payload))


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


def _registry_has(tools: Any | None, name: str) -> bool:
    if tools is None:
        return False
    if hasattr(tools, "list_tools"):
        try:
            return any(str(t.get("name")) == name for t in (tools.list_tools() or []))
        except Exception:  # noqa: BLE001
            pass
    # ToolRegistry stores in _tools
    inner = getattr(tools, "_tools", None)
    return isinstance(inner, dict) and name in inner


def _ensure_packages(
    blob: str,
    *,
    bus: Any,
    tools: Any | None,
    calls: int,
    max_tool_calls: int,
    record: list[dict[str, Any]] | None = None,
) -> tuple[list[str], int]:
    """install_tool dry_run → install if missing. Returns (context lines, calls_used)."""
    chunks: list[str] = []
    if not _registry_has(tools, "install_tool"):
        return chunks, calls

    for pkg in packages_needed(blob):
        if calls >= max_tool_calls:
            break
        # 1) status (dry_run)
        args_dry = {"package": pkg, "dry_run": True}
        st = _call_tool(tools, "install_tool", args_dry)
        calls += 1
        _emit_tool_call(bus, "install_tool", args_dry, st, record=record)

        # install_tool shape: already_installed + dry_run
        installed = bool(isinstance(st, dict) and st.get("already_installed"))

        if installed:
            chunks.append(f"install_tool: {pkg} already installed")
            continue

        if calls >= max_tool_calls:
            chunks.append(f"install_tool: {pkg} missing (budget exhausted, not installed)")
            break

        # 2) real install
        args_inst = {"package": pkg, "dry_run": False}
        res = _call_tool(tools, "install_tool", args_inst)
        calls += 1
        _emit_tool_call(bus, "install_tool", args_inst, res, record=record)
        if isinstance(res, dict) and res.get("ok"):
            chunks.append(f"install_tool: installed {pkg}")
        else:
            err = res.get("error") if isinstance(res, dict) else "install failed"
            chunks.append(f"install_tool: failed {pkg} ({err})")

    return chunks, calls


def prefetch_for_workers(
    blob: str,
    *,
    bus: Any = None,
    tools: Any | None = None,
    memory: Any | None = None,
    max_tool_calls: int = 5,
    max_urls: int = 3,
    record: list[dict[str, Any]] | None = None,
) -> str:
    """
    Run allowlisted prefetches and return a context block for workers.

    - install_tool for missing allowlisted packages named in the task
    - http(s) URLs → web_fetch (via ToolRegistry when present)
    - memory_search when hints match and vectors available
    Emits pipeline.tool_call per invocation. Caps at max_tool_calls.
    """
    text = blob or ""
    chunks: list[str] = []
    calls = 0

    # ── install missing deps (allowlist) ──────────────────────────────
    inst_lines, calls = _ensure_packages(
        text,
        bus=bus,
        tools=tools,
        calls=calls,
        max_tool_calls=max_tool_calls,
        record=record,
    )
    chunks.extend(inst_lines)

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
        _emit_tool_call(bus, "web_fetch", args, res, record=record)
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
        _emit_tool_call(bus, "memory_search", args, hits, record=record)
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
    for pkg in packages_needed(text):
        out.append(f"install_tool:{pkg}")
    if _URL_RE.search(text):
        out.append("web_fetch")
    low = text.lower()
    if any(h in low for h in _MEMORY_HINTS):
        out.append("memory_search")
    return out
