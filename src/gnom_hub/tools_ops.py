"""Core tool registration + hub_status text (extracted from Hub)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from gnom_hub.plugins.registry import ToolSpec


def _action_to_dict(result: Any) -> dict[str, Any]:
    """Normalize computer ActionResult-like objects for tools."""
    if result is None:
        return {"ok": False, "error": "no result"}
    if isinstance(result, dict):
        return result
    out: dict[str, Any] = {}
    for k in ("ok", "error", "message", "stdout", "stderr", "path", "data"):
        if hasattr(result, k):
            out[k] = getattr(result, k)
    if "ok" not in out:
        out["ok"] = not bool(out.get("error"))
    return out


class ToolsOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def _tool_memory_search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        from gnom_hub.memory.layered_search import search_layers

        return search_layers(
            query=str(query),
            hot=getattr(self, "hot", None),
            warm=getattr(self, "warm", None),
            vectors=getattr(self, "vectors", None),
            limit=int(limit),
        )

    def index_durable_fact(self, text: str, *, source: str = "warm") -> str:
        """Sync write into vector store so memory_search sees it immediately."""
        t = " ".join(str(text or "").split()).strip()
        if not t:
            return ""
        vectors = getattr(self, "vectors", None)
        if vectors is None:
            return ""
        try:
            return str(vectors.add(t, meta={"source": source}) or "")
        except Exception:  # noqa: BLE001
            return ""

    def _register_core_tools(self) -> None:
        self.tools.register(
            ToolSpec(
                name="hub_status",
                description="Return compact hub status string (stage, auth, tools, god).",
                handler=self._status_text,
                plugin="core",
                tags=("hub",),
            )
        )
        self.tools.register(
            ToolSpec(
                name="tools_list",
                description="List registered tools (name, description, tags, plugin).",
                handler=self._tool_tools_list,
                input_schema={
                    "type": "object",
                    "properties": {
                        "tag": {
                            "type": "string",
                            "description": "Optional filter: hub|memory|workspace|net|pipeline",
                        }
                    },
                },
                plugin="core",
                tags=("hub", "meta"),
            )
        )
        self.tools.register(
            ToolSpec(
                name="memory_search",
                description=(
                    "Search HOT + WARM (sync lexical) + Vector hybrid. "
                    "Hits include layer and indexed freshness flags."
                ),
                handler=self._tool_memory_search,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
                plugin="core",
                tags=("memory",),
            )
        )
        self.tools.register(
            ToolSpec(
                name="pipeline_do",
                description="Run full pipeline (brainstorm+execute) with a task",
                handler=lambda text: {
                    "stage": self.chat(str(text), full=True)["pipeline"]["stage"],
                    "results": list(self.pipeline.state.worker_results[:3]),
                },
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                plugin="core",
                tags=("pipeline",),
            )
        )
        self.tools.register(
            ToolSpec(
                name="pipeline_info",
                description="Current pipeline stage, tool_calls, quality head (read-only).",
                handler=self._tool_pipeline_info,
                plugin="core",
                tags=("pipeline", "hub"),
            )
        )
        from gnom_hub.tools.web_fetch import web_fetch

        self.tools.register(
            ToolSpec(
                name="web_fetch",
                description=(
                    "Fetch public http(s) URL as plain text. "
                    "Blocks private IPs unless GNOM_WEB_ALLOW_LOCAL=1."
                ),
                handler=lambda url, max_chars=8000: web_fetch(str(url), max_chars=int(max_chars)),
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "max_chars": {"type": "integer"},
                    },
                    "required": ["url"],
                },
                plugin="core",
                tags=("net",),
            )
        )

        # Tollgate-gated web search (Brave admit + ledger)
        try:
            from gnom_hub.tools.brave_search import brave_web_search

            self.tools.register(
                ToolSpec(
                    name="web_search",
                    description=(
                        "Web search via Brave through Tollgate (budgets, circuits, ledger). "
                        "Prefer for live facts; pair with web_fetch for page body."
                    ),
                    handler=lambda query, count=5, country="DE", search_lang="de": brave_web_search(
                        str(query),
                        count=int(count or 5),
                        country=str(country or "DE"),
                        search_lang=str(search_lang or "de"),
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "count": {"type": "integer"},
                            "country": {"type": "string"},
                            "search_lang": {"type": "string"},
                        },
                        "required": ["query"],
                    },
                    plugin="core",
                    tags=("net", "search", "tollgate"),
                )
            )
        except Exception:  # noqa: BLE001 — tollgate optional at import time
            pass

        try:
            from gnom_hub.tools.elevenlabs_budget import check_budget

            self.tools.register(
                ToolSpec(
                    name="elevenlabs_budget",
                    description=(
                        "Check ElevenLabs character budget / floor via Tollgate "
                        "(ELEVENLABS_MIN_REMAINING). cost=planned chars to spend."
                    ),
                    handler=lambda cost=0: check_budget(cost=int(cost or 0)),
                    input_schema={
                        "type": "object",
                        "properties": {"cost": {"type": "integer"}},
                    },
                    plugin="core",
                    tags=("tts", "tollgate"),
                )
            )
        except Exception:  # noqa: BLE001
            pass

        from gnom_hub.tools.browser_tools import browser_open_url

        self.tools.register(
            ToolSpec(
                name="browser_open",
                description=(
                    "Open a URL in the user's VISIBLE browser (macOS open / headed Chromium). "
                    "Use for live navigation (e.g. go to grok.com). Not for generating HTML."
                ),
                handler=lambda url: browser_open_url(str(url)),
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
                plugin="core",
            )
        )
        # Computer-use tools (handlers respect God-Mode; inspect/shell blocked when off)
        self.tools.register(
            ToolSpec(
                name="computer_inspect",
                description=(
                    "Screenshot + vision + OCR of the screen. Requires God-Mode. "
                    "Use when you need to see what is currently on the desktop."
                ),
                handler=lambda: self.computer.inspect_screen(),
                input_schema={"type": "object", "properties": {}},
                plugin="core",
            )
        )
        self.tools.register(
            ToolSpec(
                name="computer_shell",
                description=(
                    "Run a short allowlisted shell command (ls, pwd, open, cat, …). "
                    "Requires God-Mode. Prefer browser_open for URLs."
                ),
                handler=lambda cmd: _action_to_dict(self.computer.action.run_shell(str(cmd))),
                input_schema={
                    "type": "object",
                    "properties": {"cmd": {"type": "string"}},
                    "required": ["cmd"],
                },
                plugin="core",
            )
        )
        self.tools.register(
            ToolSpec(
                name="computer_type",
                description="Type text via OS keyboard (requires God-Mode).",
                handler=lambda text: _action_to_dict(self.computer.action.type_text(str(text))),
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                plugin="core",
            )
        )
        self.tools.register(
            ToolSpec(
                name="computer_click",
                description="Click screen coordinates x,y (requires God-Mode).",
                handler=lambda x, y: _action_to_dict(self.computer.action.click(int(x), int(y))),
                input_schema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                    },
                    "required": ["x", "y"],
                },
                plugin="core",
            )
        )
        # --- Agent tool stack: install + Playwright automation ---
        from gnom_hub.tools.playwright_tools import (
            browser_eval,
            browser_goto,
            browser_screenshot,
        )
        from gnom_hub.tools.tool_install import ensure_package, ensure_tool_stack

        self.tools.register(
            ToolSpec(
                name="tool_ensure",
                description=(
                    "Ensure agent tool deps via pip allowlist (playwright/pyautogui/pillow). "
                    "which=all|browser|gui. Installs missing packages; playwright also installs Chromium. "
                    "No free apt. Call this if a tool import fails."
                ),
                handler=lambda which="all": ensure_tool_stack(str(which or "all")),
                input_schema={
                    "type": "object",
                    "properties": {
                        "which": {
                            "type": "string",
                            "description": "all | browser | gui",
                        }
                    },
                },
                plugin="core",
            )
        )
        self.tools.register(
            ToolSpec(
                name="tool_ensure_package",
                description=(
                    "Install one allowlisted package if missing: playwright, pyautogui, pillow."
                ),
                handler=lambda name, install_browsers=False: ensure_package(
                    str(name), install_browsers=bool(install_browsers)
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "install_browsers": {"type": "boolean"},
                    },
                    "required": ["name"],
                },
                plugin="core",
            )
        )
        self.tools.register(
            ToolSpec(
                name="browser_goto",
                description=(
                    "Playwright headed Chromium: navigate to URL, return title/status. "
                    "Auto-ensures playwright+chromium. Prefer over browser_open for automation."
                ),
                handler=lambda url, headless=False: browser_goto(str(url), headless=bool(headless)),
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "headless": {"type": "boolean"},
                    },
                    "required": ["url"],
                },
                plugin="core",
            )
        )
        self.tools.register(
            ToolSpec(
                name="browser_screenshot",
                description=(
                    "Screenshot the active Playwright page (after browser_goto) "
                    "into data/computer_use/agent_browser.png."
                ),
                handler=lambda path="", full_page=False: browser_screenshot(
                    str(path or ""), full_page=bool(full_page)
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "full_page": {"type": "boolean"},
                    },
                },
                plugin="core",
            )
        )
        self.tools.register(
            ToolSpec(
                name="browser_eval",
                description="Evaluate a short read-only JS expression on the active Playwright page.",
                handler=lambda js="document.title": browser_eval(str(js or "document.title")),
                input_schema={
                    "type": "object",
                    "properties": {"js": {"type": "string"}},
                },
                plugin="core",
            )
        )
        self.tools.register(
            ToolSpec(
                name="tool_scenario_run",
                description=(
                    "Run forced multi-tool scenario S1–S4 (browser/shell/gui/full). "
                    "Uses real tools; for agent pipeline tests."
                ),
                handler=lambda text="S4 full tool drill": _run_scenario(self, str(text)),
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                },
                plugin="core",
            )
        )

        self.tools.register(
            ToolSpec(
                name="workspace_list",
                description="List files in hub workspace zone temp|perm|selected.",
                handler=self._tool_workspace_list,
                input_schema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "temp (default), perm, or selected",
                        }
                    },
                },
                plugin="core",
                tags=("workspace",),
            )
        )
        self.tools.register(
            ToolSpec(
                name="workspace_read",
                description="Read a workspace text file (size-capped, safe basename only).",
                handler=self._tool_workspace_read,
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "zone": {"type": "string"},
                        "max_chars": {"type": "integer"},
                    },
                    "required": ["name"],
                },
                plugin="core",
                tags=("workspace",),
            )
        )
        self.tools.register(
            ToolSpec(
                name="trace_tail",
                description="Last N light pipeline trace events (compact).",
                handler=self._tool_trace_tail,
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "1–40, default 12"},
                        "event": {
                            "type": "string",
                            "description": "Optional filter substring, e.g. tool_call",
                        },
                    },
                },
                plugin="core",
                tags=("hub", "pipeline"),
            )
        )

    def _tool_tools_list(self, tag: str = "") -> dict[str, Any]:
        tag_s = (tag or "").strip() or None
        tools = self.tools.list_tools(tag=tag_s)
        return {
            "ok": True,
            "count": len(tools),
            "tag": tag_s,
            "tools": [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "plugin": t["plugin"],
                    "tags": t.get("tags") or [],
                    "required": list((t.get("input_schema") or {}).get("required") or []),
                }
                for t in tools
            ],
        }

    def _tool_pipeline_info(self) -> dict[str, Any]:
        st = self.pipeline.state
        tcalls = list(getattr(st, "tool_calls", None) or [])
        return {
            "ok": True,
            "stage": st.stage.value if hasattr(st.stage, "value") else str(st.stage),
            "user_text_head": (st.user_text or "")[:160],
            "tool_calls_n": len(tcalls),
            "tool_calls": [{"name": c.get("name"), "ok": c.get("ok")} for c in tcalls[:12]],
            "quality_head": (getattr(st, "quality_notes", "") or "")[:400],
            "workers": len(getattr(st, "worker_outputs", None) or []),
            "error": st.error,
        }

    def _tool_workspace_list(self, zone: str = "temp") -> dict[str, Any]:
        z = (zone or "temp").strip().lower()
        if z not in ("temp", "perm", "selected"):
            return {"ok": False, "error": f"invalid zone {zone!r}; use temp|perm|selected"}
        if z == "selected":
            folder = self.workspace.selected
            files = []
            if folder.is_dir():
                for p in sorted(folder.iterdir()):
                    if p.is_file():
                        files.append({"name": p.name, "bytes": p.stat().st_size, "zone": z})
        else:
            files = self.workspace.list_files(z)
        return {"ok": True, "zone": z, "files": files, "count": len(files)}

    def _tool_workspace_read(
        self,
        name: str = "",
        zone: str = "temp",
        max_chars: int = 8000,
    ) -> dict[str, Any]:
        safe = Path(str(name or "")).name
        if not safe or safe in (".", ".."):
            return {"ok": False, "error": "name required (basename only)"}
        z = (zone or "temp").strip().lower()
        if z == "selected":
            path = self.workspace.selected / safe
        elif z == "perm":
            path = self.workspace.perm / safe
        else:
            path = self.workspace.temp / safe
            if not path.is_file():
                alt = self.workspace.perm / safe
                if alt.is_file():
                    path = alt
                    z = "perm"
        if not path.is_file():
            return {"ok": False, "error": f"not found: {safe} in {z}"}
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        cap = max(200, min(int(max_chars or 8000), 50000))
        truncated = len(raw) > cap
        return {
            "ok": True,
            "name": safe,
            "zone": z,
            "bytes": path.stat().st_size,
            "truncated": truncated,
            "text": raw[:cap],
        }

    def _tool_trace_tail(self, limit: int = 12, event: str = "") -> dict[str, Any]:
        lim = max(1, min(int(limit or 12), 40))
        events = list(getattr(self, "trace", None) or [])[-80:]
        filt = (event or "").strip().lower()
        if filt:
            events = [e for e in events if filt in str(e.get("event") or "").lower()]
        tail = events[-lim:]
        compact = []
        for e in tail:
            compact.append(
                {
                    "ts": e.get("ts"),
                    "event": e.get("event"),
                    "data": e.get("data"),
                }
            )
        return {"ok": True, "count": len(compact), "filter": filt or None, "events": compact}

    def reload_plugins(self) -> dict:
        """
        Hot-reload plugins/ from disk (no hub restart).

        Core tools stay; plugin tools are dropped and re-registered.
        Workers keep the same ToolRegistry instance — new tools appear
        on the next tool call / worker run automatically.
        """
        result = self.plugins.reload_all()
        self.plugin_list = list(result.get("plugins") or self.plugins.loaded or [])
        try:
            self.bus.emit(
                "plugins.reloaded",
                {
                    "plugins": len(self.plugin_list),
                    "removed_tools": result.get("removed_tools") or [],
                    "errors": len(result.get("errors") or []),
                },
            )
        except Exception:  # noqa: BLE001
            pass
        return {
            "ok": True,
            "plugins": self.plugin_list,
            "tools": self.tools.list_tools(),
            "removed_tools": list(result.get("removed_tools") or []),
            "errors": list(result.get("errors") or []),
            "reloaded_at": result.get("reloaded_at"),
        }

    def _status_text(self) -> str:
        st = self.pipeline.state
        auth = {}
        if hasattr(self.llm, "auth_snapshot"):
            try:
                auth = self.llm.auth_snapshot() or {}
            except Exception:  # noqa: BLE001
                auth = {}
        sys_a = auth.get("system") or "?"
        wrk_a = auth.get("worker_effective") or auth.get("worker") or "?"
        blocked = "yes" if auth.get("session_auth_blocked") else "no"
        tcalls = len(getattr(st, "tool_calls", None) or [])
        via_tg = os.getenv("GNOM_TOLLGATE_LLM", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        tg_url = (os.getenv("TOLLGATE_URL") or "").strip() or "in-process"
        tg_bit = f"tollgate={'on' if via_tg else 'off'}:{tg_url}"
        try:
            snap = self._tollgate_snapshot() if hasattr(self, "_tollgate_snapshot") else {}
            tot = (snap or {}).get("usage_totals") or {}
            if tot.get("calls") is not None:
                tg_bit += f" day_calls={tot.get('calls')} day_usd={float(tot.get('usd') or 0):.4f}"
        except Exception:  # noqa: BLE001
            pass
        owner = "tollgate" if via_tg else "gnom-legacy"
        return (
            f"stage={st.stage.value} "
            f"providers={owner} "
            f"deepseek={'yes' if self.llm.has_provider('deepseek') else 'no'} "
            f"auth_sys={sys_a} auth_worker={wrk_a} auth_blocked={blocked} "
            f"tool_calls={tcalls} "
            f"god={self.god_mode.enabled} "
            f"vectors={self.vectors.count()} "
            f"plugins={len(self.plugin_list)} "
            f"tools={len(self.tools)} "
            f"{tg_bit}"
        )


def _run_scenario(hub: object, text: str) -> dict:
    from gnom_hub.tools.tool_scenarios import run_forced_tool_scenario

    tools = getattr(hub, "tools", None)
    bus = getattr(hub, "bus", None)
    return run_forced_tool_scenario(tools, text, bus=bus)
