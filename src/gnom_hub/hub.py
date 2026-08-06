"""Application hub: wires EventBus, agents, pipeline, memory, LLM, optional Telegram."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gnom_hub.agents.manager import AgentManager
from gnom_hub.agents.models import FLEX_PRESETS, AgentId, AgentState
from gnom_hub.backup_ops import BackupOpsMixin
from gnom_hub.computer_use.workflow import ComputerUseKit
from gnom_hub.config.keys import ensure_env_from_key_txt, load_keys
from gnom_hub.config.paths import project_root
from gnom_hub.core.event_bus import EventBus
from gnom_hub.jobs import JobsMixin
from gnom_hub.llm.manager import LLMManager
from gnom_hub.memory.atomic import atomic_write_text
from gnom_hub.memory.cold import ColdArchive
from gnom_hub.memory.facade import MemoryFacade
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.memory.warm import WarmMemory
from gnom_hub.memory.wiring import MemoryWiringMixin
from gnom_hub.memory.workspace import WorkspaceStore
from gnom_hub.pipeline.orchestrator import Orchestrator as Pipeline
from gnom_hub.plugins.loader import PluginLoader
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.presets import PresetsMixin
from gnom_hub.security.god_mode import god_mode_from_env
from gnom_hub.session_ops import SessionOpsMixin
from gnom_hub.session_pack import SessionPackMixin
from gnom_hub.telegram.bot import TelegramBridge
from gnom_hub.telegram.commands import TelegramCommandMixin
from gnom_hub.ui.tooltips import TOOLTIPS


class Hub(
    TelegramCommandMixin,
    BackupOpsMixin,
    SessionPackMixin,
    JobsMixin,
    MemoryWiringMixin,
    PresetsMixin,
    SessionOpsMixin,
):
    """Single process facade used by the HTTP API and CLI."""

    def __init__(self) -> None:
        self.root = project_root()
        ensure_env_from_key_txt(self.root)
        self.keys = load_keys(self.root)
        self.bus = EventBus()
        self.agents = AgentManager(self.bus)
        self.llm = LLMManager(keys=self.keys)
        self.hot = HotMemory(self.root)
        self.warm = WarmMemory(self.root)
        self.workspace = WorkspaceStore(self.root)
        self.cold = ColdArchive(self.root)
        self.vectors = VectorStore(self.root)
        # One-shot scrub: drop HTML/meta junk left by older Memory agent runs
        try:
            n_hot = self.hot.scrub_facts()
            if n_hot:
                self.hot.save()
            self.vectors.scrub()
        except Exception:  # noqa: BLE001
            pass
        self.memory = MemoryFacade(self.hot, self.warm, self.vectors)
        self.god_mode = god_mode_from_env()
        self.computer = ComputerUseKit(self.root, god_mode=self.god_mode.enabled)
        self.tools = ToolRegistry()
        self.plugins = PluginLoader(self.root / "plugins", self.tools)
        self._register_core_tools()
        self.plugin_list = self.plugins.discover_and_load()
        self.pipeline = self._new_pipeline()
        self._jobs: dict[str, dict[str, Any]] = {}
        self.last_error: str | None = None
        # Last successful Execute snapshot for /api/export/last (survives reset)
        self._last_execute_export: dict[str, Any] | None = None
        self._agent_state_path = self.root / "data" / "hot" / "agents.json"
        self._checkpoint_path = self.root / "data" / "hot" / "checkpoint.json"
        # Light tracing (plan §8.2) — ring buffer of pipeline events
        self.trace: list[dict[str, Any]] = []
        self.ui_lang: str = os.getenv("GNOM_UI_LANG", "en").strip().lower() or "en"
        self.auto_pack_after_execute: bool = os.getenv("GNOM_AUTO_PACK", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        self._packs_dir = self.root / "data" / "packs"
        # Ensure runtime dirs exist (USB / fresh clone)
        for _d in (
            self.root / "data" / "hot",
            self.root / "data" / "warm",
            self.root / "data" / "cold",
            self.root / "data" / "backups",
            self.root / "data" / "packs",
            self.root / "data" / "workspace" / "temp",
            self.root / "data" / "workspace" / "perm",
            self.root / "data" / "workspace" / "exports",
        ):
            _d.mkdir(parents=True, exist_ok=True)
        try:
            _pm = int(os.getenv("GNOM_PACK_MAX", "30").strip() or "30")
        except ValueError:
            _pm = 30
        self.pack_max: int = max(5, min(100, _pm))
        # Feature flags (plan phase 3+ chrome can be dimmed)
        self.feature_phase3: bool = os.getenv("GNOM_PHASE3", "1").strip() not in (
            "0",
            "false",
            "no",
        )
        self._presets_path = self.root / "data" / "hot" / "worker_presets.json"
        self._team_presets_path = self.root / "data" / "hot" / "team_presets.json"
        # Coordinator plan strategy (team preset / workflow); whitelist only
        self.plan_mode: str = "default"
        self.telegram = self._init_telegram()
        self._load_agent_state()
        # Key.txt: DEEPSEEK_API_KEY = system, WORKER_API_KEY = all workers
        self._apply_keys_from_keyfile()
        # Core agents + worker1/2 on; worker3/4 stay off until user enables
        self.agents.enable_all(include_extra_workers=False)
        self._wire_memory()
        self._wire_trace()
        self.agents.on_start()
        # Auto-start telegram poll if GNOM_TELEGRAM_POLL=1
        if os.getenv("GNOM_TELEGRAM_POLL", "").strip() in ("1", "true", "yes"):
            self.telegram_start()

    def _new_pipeline(self) -> Pipeline:
        pipe = Pipeline(
            self.bus,
            llm_manager=self.llm,
            agent_manager=self.agents,
            memory=self.memory,
        )
        pipe.plan_mode = getattr(self, "plan_mode", "default") or "default"
        return pipe

    def _init_telegram(self) -> TelegramBridge:
        token = (
            self.keys.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
        ).strip()
        return TelegramBridge(self.bus, token, on_command=self._telegram_command)

    def _register_core_tools(self) -> None:
        self.tools.register(
            ToolSpec(
                name="hub_status",
                description="Return compact hub status string",
                handler=self._status_text,
                plugin="core",
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
            )
        )

    def _status_text(self) -> str:
        st = self.pipeline.state
        return (
            f"stage={st.stage.value} "
            f"deepseek={'yes' if self.llm.has_provider('deepseek') else 'no'} "
            f"god={self.god_mode.enabled} "
            f"vectors={self.vectors.count()} "
            f"plugins={len(self.plugin_list)}"
        )

    def _wire_trace(self) -> None:
        """Subscribe to pipeline events for light tracing (no heavy spans)."""

        def make_handler(event: str) -> Any:
            def _h(data: Any) -> None:
                self._append_trace(event, data)

            return _h

        for ev in (
            "pipeline.stage",
            "pipeline.brainstorm",
            "pipeline.distill",
            "pipeline.flex",
            "pipeline.coordinate",
            "pipeline.worker",
            "pipeline.quality",
            "pipeline.done",
            "pipeline.error",
            "pipeline.question",
            "pipeline.warning",
            "pipeline.brainstorm_ready",
        ):
            self.bus.on(ev, make_handler(ev))

    def _append_trace(self, event: str, data: Any) -> None:
        from datetime import datetime, timezone

        summary: Any = data
        if isinstance(data, dict):
            summary = {}
            for k, v in list(data.items())[:12]:
                if isinstance(v, str) and len(v) > 160:
                    summary[k] = v[:160] + "…"
                elif isinstance(v, list) and len(v) > 6:
                    summary[k] = f"[{len(v)} items]"
                else:
                    summary[k] = v
        self.trace.append(
            {
                "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "event": event,
                "data": summary,
            }
        )
        if len(self.trace) > 100:
            self.trace = self.trace[-100:]

    def clear_trace(self) -> dict[str, Any]:
        n = len(self.trace)
        self.trace = []
        return {"ok": True, "cleared": n, "count": 0, "trace": []}

    def export_trace(
        self,
        *,
        limit: int = 100,
        fmt: str = "json",
    ) -> dict[str, Any]:
        """Export light trace as JSON or Markdown (download helper)."""
        from datetime import datetime, timezone

        lim = max(1, min(100, int(limit)))
        events = list(self.trace[-lim:])
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fmt_l = (fmt or "json").strip().lower()
        if fmt_l in ("md", "markdown"):
            lines = [
                "# Gnom-Hub light trace",
                f"exported_at: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
                f"events: {len(events)}",
                "",
            ]
            for e in events:
                d = e.get("data")
                extra = ""
                if isinstance(d, dict):
                    bits = []
                    for k in ("stage", "worker", "error", "label", "id", "name"):
                        if d.get(k) is not None:
                            bits.append(f"{k}={d.get(k)}")
                    if not bits and d:
                        bits.append(str(list(d.keys())[:6]))
                    extra = " ".join(str(b) for b in bits)
                elif d is not None:
                    extra = str(d)[:120]
                lines.append(f"- `{e.get('ts') or ''}` **{e.get('event') or ''}** {extra}".rstrip())
            body = chr(10).join(lines) + chr(10)
            filename = f"gnom-hub-trace-{stamp}.md"
            return {
                "ok": True,
                "format": "markdown",
                "filename": filename,
                "content": body,
                "count": len(events),
            }
        import json as _json

        body = _json.dumps(
            {
                "format": "gnom-hub-trace",
                "format_version": 1,
                "app_version": "3.7.1",
                "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "count": len(events),
                "trace": events,
            },
            ensure_ascii=False,
            indent=2,
        ) + chr(10)
        filename = f"gnom-hub-trace-{stamp}.json"
        return {
            "ok": True,
            "format": "json",
            "filename": filename,
            "content": body,
            "count": len(events),
        }

    def export_workspace_zip(self, zone: str = "all") -> dict[str, Any]:
        path = self.workspace.export_zip(zone)
        self._append_trace(
            "workspace.export",
            {"zone": zone, "name": path.name, "bytes": path.stat().st_size},
        )
        return {
            "ok": True,
            "name": path.name,
            "path": str(path),
            "bytes": path.stat().st_size,
            "zone": zone,
        }

    def workspace_export_path(self, name: str) -> Path:
        """Safe path under data/workspace/exports for download."""
        safe = Path(name).name
        if not safe.startswith("gnom-hub-workspace-") or not safe.endswith(".zip"):
            raise ValueError("invalid workspace export name")
        export_dir = (self.root / "data" / "workspace" / "exports").resolve()
        path = (export_dir / safe).resolve()
        if not str(path).startswith(str(export_dir)) or not path.is_file():
            raise FileNotFoundError(safe)
        return path

    def _apply_keys_from_keyfile(self) -> None:
        """
        Map Key.txt onto agents:
          DEEPSEEK_API_KEY / SYSTEM → brainstorm, memory, flex, coordinator
          WORKER_API_KEY / WORKER → worker1–4
          DEEPSEEK_MODEL → default + every agent model
        """
        system_key = (self.keys.get("DEEPSEEK_API_KEY") or "").strip() or None
        worker_key = (self.keys.get("WORKER_API_KEY") or "").strip() or None
        model = (self.keys.get("DEEPSEEK_MODEL") or "").strip() or None
        if model:
            self.llm.default_model = model
        system_ids = (
            AgentId.BRAINSTORM,
            AgentId.MEMORY,
            AgentId.FLEX,
            AgentId.COORDINATOR,
        )
        worker_ids = (
            AgentId.WORKER1,
            AgentId.WORKER2,
            AgentId.WORKER3,
            AgentId.WORKER4,
        )
        if system_key:
            for aid in system_ids:
                try:
                    self.agents.get(aid).api_key = system_key
                except ValueError:
                    pass
        if worker_key:
            for aid in worker_ids:
                try:
                    self.agents.get(aid).api_key = worker_key
                except ValueError:
                    pass
        if model:
            for a in self.agents.list_agents():
                a.model = model
        if not system_key and not worker_key and not model:
            return
        # Keep agents.json in sync (gitignored)
        try:
            self._save_agent_state()
        except OSError:
            pass

    def _load_agent_state(self) -> None:
        path = self._agent_state_path
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        agents = data.get("agents") if isinstance(data, dict) else None
        if not isinstance(agents, list):
            return
        for item in agents:
            if not isinstance(item, dict):
                continue
            aid = item.get("id")
            if not aid:
                continue
            try:
                agent = self.agents.get(aid)
            except ValueError:
                continue
            if agent.toggleable and "enabled" in item:
                agent.enabled = bool(item["enabled"])
            if agent.id == AgentId.FLEX and item.get("preset"):
                try:
                    self.agents.set_flex_preset(str(item["preset"]))
                except ValueError:
                    pass
            if item.get("model"):
                agent.model = str(item["model"])
            if item.get("api_key") is not None:
                k = str(item["api_key"]).strip()
                agent.api_key = k or None
            if "tts" in item:
                agent.tts = bool(item["tts"])
            if item.get("system_prompt") is not None:
                agent.system_prompt = str(item["system_prompt"]) or None
            for key in (
                "temperature",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
            ):
                if item.get(key) is not None:
                    try:
                        setattr(agent, key, float(item[key]))
                    except (TypeError, ValueError):
                        pass
            if item.get("max_tokens") is not None:
                try:
                    agent.max_tokens = int(item["max_tokens"])
                except (TypeError, ValueError):
                    pass

    def _save_agent_state(self) -> Path:
        payload = {
            "agents": [
                {
                    "id": a.id.value,
                    "enabled": a.enabled,
                    "preset": a.preset,
                    "model": a.model,
                    # Per-agent keys stay under data/ (gitignored) — never log them
                    "api_key": a.api_key,
                    "tts": a.tts,
                    "system_prompt": a.system_prompt,
                    "temperature": a.temperature,
                    "top_p": a.top_p,
                    "max_tokens": a.max_tokens,
                    "frequency_penalty": a.frequency_penalty,
                    "presence_penalty": a.presence_penalty,
                }
                for a in self.agents.list_agents()
            ]
        }
        path = self._agent_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return path

    # ── serialization ───────────────────────────────────────────────

    def _agent_dict(self, a: AgentState) -> dict[str, Any]:
        usage = self.llm.usage_snapshot()["by_agent"].get(a.id.value, {})
        tokens = int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0))
        has_llm = (
            bool(a.api_key) or self.llm.has_provider("deepseek") or self.llm.has_provider("ollama")
        )
        online = a.enabled and has_llm
        return {
            "id": a.id.value,
            "name": a.name,
            "role": a.role,
            "color": a.color,
            "enabled": a.enabled,
            "toggleable": a.toggleable,
            "preset": a.preset,
            "model": a.model or self.llm.default_model,
            "has_key": has_llm,
            "online": online,
            "tts": bool(a.tts),
            "system_prompt": a.system_prompt or "",
            "temperature": a.temperature,
            "top_p": a.top_p,
            "max_tokens": a.max_tokens,
            "frequency_penalty": a.frequency_penalty,
            "presence_penalty": a.presence_penalty,
            "tokens": tokens,
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "cost_usd": float(usage.get("cost_usd", 0.0)),
            "calls": int(usage.get("calls", 0)),
        }

    def pipeline_dict(self) -> dict[str, Any]:
        st = self.pipeline.state
        q = None
        if st.pending_question is not None:
            q = {
                "id": st.pending_question.id,
                "text": st.pending_question.text,
                "options": list(st.pending_question.options),
            }
        can_execute = bool((st.brainstorm_notes or "").strip()) and st.stage.value in (
            "brainstorm",
            "idle",
            "done",
            "error",
        )
        if st.stage.value in ("distill", "flex", "coordinate", "work", "clarify"):
            can_execute = False
        return {
            "stage": st.stage.value,
            "mode": getattr(st, "mode", "brainstorm") or "brainstorm",
            "user_text": st.user_text,
            "memory_context": st.memory_context,
            "brainstorm_notes": st.brainstorm_notes,
            "brainstorm_turns": list(getattr(st, "brainstorm_turns", None) or []),
            "can_execute": can_execute,
            "distilled_requirements": list(st.distilled_requirements),
            "flex_notes": st.flex_notes,
            "pending_question": q,
            "worker_results": list(st.worker_results),
            "worker_outputs": list(st.worker_outputs or []),
            "quality_notes": getattr(st, "quality_notes", "") or "",
            "warnings": list(st.warnings),
            "error": st.error,
        }

    def memory_dict(self) -> dict[str, Any]:
        return {
            "summary": self.hot.get_context_summary(),
            "facts": self.hot.all_facts()[-30:],
            "hot_count": len(self.hot.all_facts()),
            "warm_facts": self.warm.all_facts()[-30:],
            "warm_count": len(self.warm.all_facts()),
            "recent_messages": self.hot.recent_messages(6),
            "context": self.memory.pipeline_context(),
            "canvas_nodes": len(self.hot.canvas.nodes),
        }

    def snapshot(self) -> dict[str, Any]:
        usage = self.llm.usage_snapshot()
        return {
            "agents": [self._agent_dict(a) for a in self.agents.list_agents()],
            "pipeline": self.pipeline_dict(),
            "memory_summary": self.hot.get_context_summary(),
            "memory": self.memory_dict(),
            "workspace": self.workspace.snapshot(),
            "telegram": {
                "configured": self.telegram.enabled,
                "running": self.telegram.running,
            },
            "god_mode": self.god_mode.snapshot(),
            "vectors": {"count": self.vectors.count()},
            "cold": {"count": len(self.cold.list_archives(200))},
            "plugins": self.plugin_list,
            "tools": self.tools.list_tools(),
            "computer_use": self.computer.snapshot(),
            "canvas": {
                "mermaid": self.hot.canvas.to_mermaid(),
                "nodes": len(self.hot.canvas.nodes),
            },
            "llm": {
                "deepseek": self.llm.has_provider("deepseek"),
                "ollama": self.llm.has_provider("ollama"),
                "free_only": self.llm.free_only,
                "max_budget_usd": self.llm.max_budget_usd,
                "spent_usd": usage["spent_usd"],
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "default_model": self.llm.default_model,
                "providers": self.llm.providers_snapshot(),
            },
            "version": "3.7.1",
            "flex_presets": list(FLEX_PRESETS),
            "plan_mode": getattr(self, "plan_mode", "default") or "default",
            "team_presets": self.list_team_presets(),
            "last_error": self.last_error,
            "trace": list(self.trace[-40:]),
            "ui_lang": self.ui_lang,
            "checkpoint": {
                "exists": self._checkpoint_path.is_file(),
                "path": str(self._checkpoint_path),
            },
            "features": {
                "phase3": self.feature_phase3,
                "workers_max": 4,
            },
            "worker_presets": self.list_worker_presets(),
        }

    def archive_cold(self, label: str = "") -> dict[str, Any]:
        meta = self.cold.archive_hot(
            session=dict(self.hot.session),
            canvas_mmd=self.hot.canvas.to_mermaid(),
            label=label,
        )
        return {"ok": True, "archive": meta}

    def restore_cold(
        self,
        archive_id: str,
        *,
        archive_current: bool = True,
    ) -> dict[str, Any]:
        """Restore a COLD archive into HOT (optionally archive current HOT first)."""
        data = self.cold.get(archive_id)
        if not data:
            raise FileNotFoundError(archive_id)
        archived = None
        if archive_current:
            sess = self.hot.session or {}
            if sess.get("messages") or sess.get("facts"):
                archived = self.archive_cold(label="pre-restore").get("archive")
        session = data.get("session") if isinstance(data.get("session"), dict) else {}
        self.hot.session = {
            "messages": list(session.get("messages") or []),
            "facts": list(session.get("facts") or []),
            "updated_at": session.get("updated_at") or "",
        }
        canvas = str(data.get("canvas") or "")
        if canvas.strip():
            self.hot.canvas_path.parent.mkdir(parents=True, exist_ok=True)
            nl = chr(10)
            if not canvas.endswith(nl):
                canvas = canvas + nl
            atomic_write_text(self.hot.canvas_path, canvas)
            self.hot.canvas.load(self.hot.canvas_path)
        else:
            self.hot.canvas.clear()
        self.hot.save()
        meta = data.get("meta") or {"id": archive_id}
        self._append_trace(
            "cold.restore",
            {"id": meta.get("id") or archive_id, "label": meta.get("label")},
        )
        snap = self.snapshot()
        snap["ok"] = True
        snap["restored"] = meta
        if archived:
            snap["archived_previous"] = archived
        return snap

    def delete_cold(self, archive_id: str) -> dict[str, Any]:
        ok = self.cold.delete(archive_id)
        if not ok:
            raise FileNotFoundError(archive_id)
        self._append_trace("cold.delete", {"id": archive_id})
        return {
            "ok": True,
            "deleted": archive_id,
            "archives": self.cold.list_archives()[:30],
        }

    def set_god_mode(self, enabled: bool, reason: str = "api") -> dict[str, Any]:
        if enabled:
            self.god_mode.enable(reason)
        else:
            self.god_mode.disable(reason)
        self.computer.set_god_mode(self.god_mode.enabled)
        return self.god_mode.snapshot()

    # ── commands ────────────────────────────────────────────────────

    def chat(self, text: str, *, full: bool = False) -> dict[str, Any]:
        """Synchronous chat. Default: brainstorm turn. full=True: whole pipeline."""
        return self.chat_sync(text, full=full)

    def _pipeline_lock_obj(self) -> Any:
        import threading

        if not hasattr(self, "_pipeline_lock"):
            self._pipeline_lock = threading.Lock()
        return self._pipeline_lock

    def chat_sync(self, text: str, *, full: bool = False) -> dict[str, Any]:
        self.last_error = None
        self.memory.set_query_hint(text)
        with self._pipeline_lock_obj():
            if full:
                self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
                self.pipeline.start(text)
            else:
                self.pipeline.brainstorm_turn(text)
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            elif full and self.pipeline.state.stage.value == "done":
                self._capture_workspace_outputs()
                self._remember_execute_export()
            return self.snapshot()

    def execute_sync(self) -> dict[str, Any]:
        """Run distill → flex → workers from accumulated brainstorm."""
        self.last_error = None
        with self._pipeline_lock_obj():
            # Single source: hub.plan_mode → pipeline before coordinate
            self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
            self.pipeline.execute()
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            elif self.pipeline.state.stage.value == "done":
                self._capture_workspace_outputs()
                self._remember_execute_export()
                self.maybe_auto_pack()
            return self.snapshot()

    def _remember_execute_export(self) -> None:
        """Pin last successful Execute so export survives reset / new chat."""
        from datetime import datetime, timezone

        st = self.pipeline.state
        if st.stage.value != "done":
            return
        if not (st.worker_outputs or st.brainstorm_notes):
            return
        self._last_execute_export = {
            "stage": st.stage.value,
            "user_text": st.user_text or "",
            "brainstorm_notes": st.brainstorm_notes or "",
            "distilled_requirements": list(st.distilled_requirements or []),
            "flex_notes": st.flex_notes or "",
            "quality_notes": st.quality_notes or "",
            "worker_outputs": list(st.worker_outputs or []),
            "saved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }

    def build_export_last(self) -> dict[str, Any]:
        """Markdown export: live pipeline if it has workers, else pinned Execute."""
        st = self.pipeline.state
        pinned = getattr(self, "_last_execute_export", None)
        use_live = bool(st.worker_outputs) or (
            st.stage.value == "done" and (st.brainstorm_notes or "").strip()
        )
        if use_live:
            src = {
                "stage": st.stage.value,
                "user_text": st.user_text or "",
                "brainstorm_notes": st.brainstorm_notes or "",
                "distilled_requirements": list(st.distilled_requirements or []),
                "flex_notes": st.flex_notes or "",
                "quality_notes": st.quality_notes or "",
                "worker_outputs": list(st.worker_outputs or []),
                "source": "live",
            }
        elif isinstance(pinned, dict) and (
            pinned.get("worker_outputs") or pinned.get("brainstorm_notes")
        ):
            src = dict(pinned)
            src["source"] = "pinned"
        else:
            src = {
                "stage": st.stage.value,
                "user_text": st.user_text or "",
                "brainstorm_notes": st.brainstorm_notes or "",
                "distilled_requirements": list(st.distilled_requirements or []),
                "flex_notes": st.flex_notes or "",
                "quality_notes": st.quality_notes or "",
                "worker_outputs": list(st.worker_outputs or []),
                "source": "empty",
            }
        parts = [
            "# Gnom-Hub export",
            f"stage={src.get('stage')}",
            f"user={src.get('user_text')}",
            f"source={src.get('source')}",
            "",
            "## Brainstorm",
            str(src.get("brainstorm_notes") or "(none)"),
            "",
            "## Requirements",
            "\n".join(f"- {r}" for r in (src.get("distilled_requirements") or [])) or "(none)",
            "",
            "## Flex",
            str(src.get("flex_notes") or "(none)"),
            "",
            "## Quality",
            str(src.get("quality_notes") or "(none)"),
            "",
        ]
        for out in src.get("worker_outputs") or []:
            if not isinstance(out, dict):
                continue
            parts.append(f"## {out.get('name') or out.get('worker')}")
            parts.append(f"Task: {out.get('task') or ''}")
            parts.append(str(out.get("result") or ""))
            parts.append("")
        text = "\n".join(parts)
        return {
            "ok": True,
            "filename": "gnom-hub-export.md",
            "content": text,
            "chars": len(text),
            "source": src.get("source"),
            "saved_at": src.get("saved_at"),
        }

    def _capture_workspace_outputs(self) -> None:
        """Write worker results into temp workspace (plan: dual workspace)."""
        st = self.pipeline.state
        for out in st.worker_outputs or []:
            wid = str(out.get("worker") or "worker")
            body = str(out.get("result") or "").strip()
            if not body:
                continue
            # Prefer .html when content looks like HTML
            low = body.lower()
            ext = ".html" if ("<!doctype" in low or "<html" in low) else ".txt"
            name = f"{wid}_{st.stage.value}{ext}"
            try:
                self.workspace.write_text("temp", name, body)
            except Exception as exc:  # noqa: BLE001
                self._append_trace("workspace.write_error", {"name": name, "error": str(exc)})
        if st.brainstorm_notes:
            try:
                self.workspace.write_text(
                    "temp",
                    "brainstorm_latest.txt",
                    st.brainstorm_notes[:8000],
                )
            except Exception as exc:  # noqa: BLE001
                self._append_trace(
                    "workspace.write_error",
                    {"name": "brainstorm_latest.txt", "error": str(exc)},
                )

    def rerun_worker_sync(self, worker_id: str) -> dict[str, Any]:
        """Re-run one worker from last task."""
        self.last_error = None
        with self._pipeline_lock_obj():
            self.pipeline.rerun_worker(worker_id)
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            elif self.pipeline.state.stage.value == "done":
                self._capture_workspace_outputs()
            return self.snapshot()

    def usage_dict(self) -> dict[str, Any]:
        snap = self.llm.usage_snapshot()
        return {
            "spent_usd": snap.get("spent_usd", 0.0),
            "prompt_tokens": snap.get("prompt_tokens", 0),
            "completion_tokens": snap.get("completion_tokens", 0),
            "by_agent": snap.get("by_agent") or {},
            "free_only": self.llm.free_only,
            "max_budget_usd": self.llm.max_budget_usd,
        }

    def reset_usage(self) -> dict[str, Any]:
        data = self.llm.reset_usage()
        self._append_trace("usage.reset", {"ok": True})
        return {"ok": True, **data, **self.usage_dict()}

    def add_hot_fact(self, text: str) -> dict[str, Any]:
        ok = self.hot.add_fact(text)
        if ok:
            self.hot.save()
        return {
            "ok": ok,
            "facts": self.hot.all_facts()[-30:],
            "hot_count": len(self.hot.all_facts()),
        }

    def delete_hot_fact(
        self, *, text: str | None = None, index: int | None = None
    ) -> dict[str, Any]:
        removed = None
        if index is not None:
            removed = self.hot.remove_fact_at(int(index))
            if removed is None:
                raise FileNotFoundError("index out of range")
        elif text and text.strip():
            ok = self.hot.remove_fact(text.strip())
            if not ok:
                raise FileNotFoundError("fact not found")
            removed = text.strip()
        else:
            raise ValueError("text or index required")
        self.hot.save()
        return {
            "ok": True,
            "removed": removed,
            "facts": self.hot.all_facts()[-30:],
            "hot_count": len(self.hot.all_facts()),
        }

    def clear_hot_facts(self) -> dict[str, Any]:
        n = self.hot.clear_facts()
        self.hot.save()
        return {"ok": True, "cleared": n, "facts": [], "hot_count": 0}

    def promote_hot_fact(self, text: str) -> dict[str, Any]:
        """Copy a HOT fact into WARM (durable)."""
        t = " ".join(str(text).split()).strip()
        if not t:
            raise ValueError("text required")
        facts = self.hot.all_facts()
        if t not in facts:
            # allow promote by index via caller resolving text
            raise FileNotFoundError("HOT fact not found")
        added = self.warm.add_fact(t)
        return {
            "ok": True,
            "promoted": t,
            "warm_added": added,
            "facts": self.hot.all_facts()[-30:],
            "warm_facts": self.warm.all_facts()[-30:],
        }

    def clarify(self, option: str) -> dict[str, Any]:
        """Synchronous clarify (also used after async reaches clarify)."""
        self.last_error = None
        with self._pipeline_lock_obj():
            self.pipeline.answer_clarify(option)
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            return self.snapshot()

    def toggle_agent(self, agent_id: str) -> dict[str, Any]:
        enabled = self.agents.toggle(agent_id)
        return {
            "id": agent_id,
            "enabled": enabled,
            "agents": [self._agent_dict(a) for a in self.agents.list_agents()],
        }

    def set_flex_preset(self, name: str) -> dict[str, Any]:
        self.agents.set_flex_preset(name)
        return self._agent_dict(self.agents.get(AgentId.FLEX))

    def set_agent_llm(
        self,
        agent_id: str,
        *,
        model: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        agent = self.agents.get(agent_id)
        if model is not None:
            agent.model = model.strip() or None
        if api_key is not None:
            agent.api_key = api_key.strip() or None
        self.agents.emit_status(agent_id)
        self._save_agent_state()
        return self._agent_dict(agent)

    def set_agent_tune(self, agent_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update per-agent prompt, LLM knobs, and TTS flag (plan tuning panel)."""
        agent = self.agents.get(agent_id)
        if "model" in fields and fields["model"] is not None:
            agent.model = str(fields["model"]).strip() or None
        if "api_key" in fields and fields["api_key"] is not None:
            key = str(fields["api_key"]).strip()
            agent.api_key = key or None
        if "system_prompt" in fields:
            sp = fields["system_prompt"]
            agent.system_prompt = (str(sp).strip() if sp is not None else "") or None
        if "tts" in fields and fields["tts"] is not None:
            agent.tts = bool(fields["tts"])
        if "temperature" in fields:
            agent.temperature = (
                None if fields["temperature"] is None else float(fields["temperature"])
            )
        if "top_p" in fields:
            agent.top_p = None if fields["top_p"] is None else float(fields["top_p"])
        if "max_tokens" in fields:
            agent.max_tokens = None if fields["max_tokens"] is None else int(fields["max_tokens"])
        if "frequency_penalty" in fields:
            agent.frequency_penalty = (
                None if fields["frequency_penalty"] is None else float(fields["frequency_penalty"])
            )
        if "presence_penalty" in fields:
            agent.presence_penalty = (
                None if fields["presence_penalty"] is None else float(fields["presence_penalty"])
            )
        self.agents.emit_status(agent_id)
        self._save_agent_state()
        return self._agent_dict(agent)

    def set_system(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Global free_only / budget / UI lang (system panel)."""
        if "free_only" in fields and fields["free_only"] is not None:
            self.llm.free_only = bool(fields["free_only"])
        if "max_budget_usd" in fields:
            raw = fields["max_budget_usd"]
            if raw is None or raw == "":
                self.llm.max_budget_usd = None
            else:
                self.llm.max_budget_usd = float(raw)
        if fields.get("default_model"):
            self.llm.default_model = str(fields["default_model"]).strip()
        if fields.get("ui_lang"):
            lang = str(fields["ui_lang"]).strip().lower()
            if lang in ("en", "de"):
                self.ui_lang = lang
        if "auto_pack_after_execute" in fields and fields["auto_pack_after_execute"] is not None:
            self.auto_pack_after_execute = bool(fields["auto_pack_after_execute"])
        if "pack_max" in fields and fields["pack_max"] is not None:
            try:
                self.pack_max = max(5, min(100, int(fields["pack_max"])))
            except (TypeError, ValueError):
                pass
        return self.system_dict()

    def system_dict(self) -> dict[str, Any]:
        usage = self.llm.usage_snapshot()
        return {
            "deepseek": self.llm.has_provider("deepseek"),
            "ollama": self.llm.has_provider("ollama"),
            "free_only": self.llm.free_only,
            "max_budget_usd": self.llm.max_budget_usd,
            "spent_usd": usage["spent_usd"],
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "default_model": self.llm.default_model,
            "god_mode": self.god_mode.enabled,
            "ui_lang": self.ui_lang,
            "checkpoint_exists": self._checkpoint_path.is_file(),
            "version": "3.7.1",
            "providers": self.llm.providers_snapshot(),
            "backups": self.list_backups()[:8],
            "packs": self.list_session_packs()[:12],
            "auto_pack_after_execute": self.auto_pack_after_execute,
            "pack_max": self.pack_max,
        }

    def telegram_start(self) -> dict[str, Any]:
        ok = self.telegram.start()
        return {"ok": ok, "running": self.telegram.running, "configured": self.telegram.enabled}

    def telegram_stop(self) -> dict[str, Any]:
        self.telegram.stop()
        return {"ok": True, "running": False}

    def telegram_inbound(self, text: str, chat_id: int | None = None) -> dict[str, Any]:
        reply = self.telegram.handle_text(text, chat_id)
        return {"reply": reply, "snapshot": self.snapshot()}

    def restore_for_reexecute(
        self,
        *,
        user_text: str,
        brainstorm_notes: str,
        brainstorm_turns: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Restore brainstorm context so a subsequent Execute re-runs workers."""
        from gnom_hub.pipeline.models import PipelineStage, PipelineState

        text = (user_text or "").strip()
        notes = (brainstorm_notes or "").strip()
        if not text and not notes:
            raise ValueError("nothing to re-execute")
        turns = list(brainstorm_turns or [])
        if not notes and turns:
            # format like orchestrator
            lines: list[str] = []
            for t in turns:
                role = str(t.get("role") or "")
                ttxt = str(t.get("text") or "").strip()
                if not ttxt:
                    continue
                if role == "user":
                    lines.append(f"You: {ttxt}")
                else:
                    lines.append(f"Brainstorm:\n{ttxt}")
                lines.append("")
            notes = "\n".join(lines).strip()
        if not text and turns:
            for t in turns:
                if t.get("role") == "user" and str(t.get("text") or "").strip():
                    text = str(t["text"]).strip()
                    break
        self.pipeline._state = PipelineState(
            stage=PipelineStage.brainstorm,
            mode="brainstorm",
            user_text=text,
            brainstorm_notes=notes,
            brainstorm_turns=turns,
        )
        self.last_error = None
        self._append_trace("session.reexecute.restore", {"user": text[:80]})
        return self.snapshot()

    def help_text(self) -> dict[str, Any]:

        return {
            "title": "Gnom-Hub help",
            "how_to": (
                "1) Send / Enter = brainstorm turn. "
                "2) Execute / Ctrl+Enter = distill + workers. "
                "3) Send+Execute = one shot after typing. "
                "4) Ctrl/⌘+S = save HOT + agents. "
                "5) Esc = close fullscreen or cancel job. "
                "6) Box 3: Copy/DL/Tab/WS/↑perm/fullscreen; toolbar Copy all + Diff + History. "
                "7) Cost badge + Compact density; job timer while busy. "
                "8) Auto-save + Box 3 focus after successful Execute. 9) Session packs (chat/history/workspace/ui_prefs/notes; list filter). 10) History Re-Exec. 11) Telegram: /hot /tools /fetch /ws /jobs /usage /backup …"
            ),
            "example": "Type idea → Execute → Pack ↓ (USB) → History Re-Exec → Diff.",
            "pipeline": "Brainstorm → Execute → Distill → Flex → Workers (1–4) → Quality → Memory",
            "keys": (
                "Keyboard: Enter send · Ctrl/⌘+Enter execute · Ctrl/⌘+S save · Esc cancel/close overlay. "
                "DEEPSEEK_API_KEY or Ollama. TELEGRAM optional."
            ),
        }

    def canvas(self) -> dict[str, Any]:
        return {
            "mermaid": self.hot.canvas.to_mermaid(),
            "nodes": list(self.hot.canvas.nodes),
            "path": str(self.hot.canvas_path),
        }

    def tooltips(self, lang: str = "en") -> dict[str, Any]:
        out: dict[str, Any] = {}
        for tip_id, langs in TOOLTIPS.items():
            block = langs.get(lang) or langs.get("en")
            if block:
                out[tip_id] = dict(block)
        return out


_HUB: Hub | None = None


def get_hub() -> Hub:
    global _HUB
    if _HUB is None:
        _HUB = Hub()
    return _HUB


def reset_hub() -> Hub:
    global _HUB
    if _HUB is not None:
        try:
            _HUB.telegram_stop()
        except Exception as exc:  # noqa: BLE001
            # Shutdown best-effort; never block hub rebuild in tests
            _ = exc
    _HUB = Hub()
    return _HUB
