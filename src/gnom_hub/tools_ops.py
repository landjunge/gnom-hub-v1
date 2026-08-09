"""Core tool registration + hub_status text (extracted from Hub)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gnom_hub.plugins.registry import ToolSpec


class ToolsOpsMixin:
    """Mixin extracted from Hub — pure move."""

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
                description="Lexical vector search over stored docs",
                handler=lambda query, limit=5: self.vectors.search(str(query), limit=int(limit)),
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
        return (
            f"stage={st.stage.value} "
            f"deepseek={'yes' if self.llm.has_provider('deepseek') else 'no'} "
            f"auth_sys={sys_a} auth_worker={wrk_a} auth_blocked={blocked} "
            f"tool_calls={tcalls} "
            f"god={self.god_mode.enabled} "
            f"vectors={self.vectors.count()} "
            f"plugins={len(self.plugin_list)} "
            f"tools={len(self.tools)}"
        )
