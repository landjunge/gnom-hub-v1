"""Application hub: wires EventBus, agents, pipeline, memory, LLM, optional Telegram."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gnom_hub.agents.manager import AgentManager
from gnom_hub.agents.models import FLEX_PRESETS, AgentId, AgentState
from gnom_hub.computer_use.workflow import ComputerUseKit
from gnom_hub.config.keys import ensure_env_from_key_txt, load_keys
from gnom_hub.config.paths import project_root
from gnom_hub.core.event_bus import EventBus
from gnom_hub.llm.manager import LLMManager
from gnom_hub.memory.atomic import atomic_write_text
from gnom_hub.memory.cold import ColdArchive
from gnom_hub.memory.facade import MemoryFacade
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.memory.warm import WarmMemory
from gnom_hub.memory.workspace import WorkspaceStore
from gnom_hub.pipeline.orchestrator import Orchestrator as Pipeline
from gnom_hub.plugins.loader import PluginLoader
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.security.god_mode import god_mode_from_env
from gnom_hub.telegram.bot import TelegramBridge
from gnom_hub.telegram.commands import TelegramCommandMixin
from gnom_hub.ui.tooltips import TOOLTIPS


class Hub(TelegramCommandMixin):
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

    def _wire_memory(self) -> None:
        def on_memory_hint(data: Any) -> None:
            if not isinstance(data, dict):
                return
            from gnom_hub.agents.roles_helpers import _is_garbage_fact

            user_text = str(data.get("user_text") or "").strip()
            if user_text:
                self.hot.add_message("user", user_text[:500])
            notes = str(data.get("brainstorm_notes") or "").strip()
            if notes:
                self.hot.add_message("brainstorm", notes[:800])
            flex = str(data.get("flex_notes") or "").strip()
            if flex:
                self.hot.add_message("flex", flex[:500])
            # HOT: clean requirements only — never HTML / meta
            for req in (data.get("requirements") or [])[:5]:
                text = str(req).strip()
                if (
                    8 <= len(text) <= 160
                    and not text.startswith("Flex/")
                    and not _is_garbage_fact(text)
                ):
                    self.hot.add_fact(text)
                    self.vectors.add(text, meta={"source": "requirement"})
            # Goal lines are durable (WARM)
            for req in data.get("requirements") or []:
                text = str(req).strip()
                low = text.lower()
                if low.startswith(("ziel:", "goal:")):
                    if 8 <= len(text) <= 160 and not _is_garbage_fact(text):
                        self.warm.add_fact(text)
                    break
            # Worker outputs: short text notes only — never code/HTML bodies
            for res in (data.get("results") or [])[:2]:
                snippet = str(res).strip()
                if "```" in snippet:
                    snippet = snippet.split("```", 1)[0].strip()
                snippet = snippet[:280]
                if (
                    snippet
                    and len(snippet) >= 20
                    and not _is_garbage_fact(snippet)
                    and not snippet.lstrip().startswith("<")
                ):
                    self.hot.add_message("worker", snippet)
            self.hot.save()

        def on_error(data: Any) -> None:
            if isinstance(data, dict):
                self.last_error = str(data.get("error") or "pipeline error")
            else:
                self.last_error = str(data)

        def on_memory_curated(data: Any) -> None:
            """LLM-extracted durable facts from Memory agent → WARM (+ HOT mirror)."""
            if not isinstance(data, dict):
                return
            from gnom_hub.agents.roles_helpers import _is_garbage_fact

            for fact in data.get("facts") or []:
                text = str(fact).strip()
                if 8 <= len(text) <= 200 and not _is_garbage_fact(text):
                    self.hot.add_fact(text)
                    self.warm.add_fact(text)
                    self.vectors.add(text, meta={"source": "memory_agent"})
            self.hot.save()

        def on_done(_data: Any) -> None:
            # Scrub + compress after each successful pipeline finish
            try:
                self.hot.scrub_facts()
                self.hot.compress_if_needed()
                self.hot.save()
            except Exception as exc:  # noqa: BLE001
                self._append_trace("compress.error", {"error": str(exc)})

        self.bus.on("pipeline.memory_hint", on_memory_hint)
        self.bus.on("pipeline.memory_curated", on_memory_curated)
        self.bus.on("pipeline.error", on_error)
        self.bus.on("pipeline.done", on_done)

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

    def _start_job(self, name: str, runner: Any) -> dict[str, Any]:
        import threading
        import uuid
        from datetime import datetime, timezone

        if not hasattr(self, "_jobs"):
            self._jobs: dict[str, dict[str, Any]] = {}
        lock = self._pipeline_lock_obj()

        job_id = uuid.uuid4().hex[:12]
        job: dict[str, Any] = {
            "id": job_id,
            "name": name,
            "status": "running",
            "stage": "queued",
            "error": None,
            "snapshot": None,
            "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        self._jobs[job_id] = job
        # ring-buffer: never drop still-running/queued jobs
        if len(self._jobs) > 40:
            for old_id in list(self._jobs.keys())[: len(self._jobs) - 40]:
                st = self._jobs.get(old_id, {}).get("status")
                if st not in ("running", "queued"):
                    self._jobs.pop(old_id, None)
        self.last_error = None

        def _finalize_job(stage_val: str | None = None) -> None:
            """Terminal status — cancel always wins (including vs exception)."""
            if job.get("cancel"):
                job["status"] = "cancelled"
                job["error"] = job.get("error") or "cancelled by user"
                job["stage"] = "cancelled"
                return
            sv = stage_val or "error"
            if sv == "error":
                self.last_error = self.pipeline.state.error
                job["status"] = "error"
                job["error"] = self.pipeline.state.error or job.get("error") or "error"
                job["stage"] = sv
            elif sv == "clarify":
                job["status"] = "clarify"
                job["stage"] = sv
            else:
                job["status"] = "done"
                job["stage"] = sv
                if name in ("execute", "pipeline", "worker_rerun"):
                    self._capture_workspace_outputs()
                    if name in ("execute", "pipeline"):
                        self._remember_execute_export()
                    if name == "execute":
                        self.maybe_auto_pack()

        def _run() -> None:
            with lock:
                handlers_on = False

                def _on_stage(data: Any) -> None:
                    if job.get("cancel"):
                        return
                    if getattr(self, "_active_job_id", None) != job_id:
                        return
                    if isinstance(data, dict) and data.get("stage"):
                        job["stage"] = str(data["stage"])
                        try:
                            job["snapshot"] = self.snapshot()
                        except Exception as exc:  # noqa: BLE001
                            job["snapshot_error"] = str(exc)

                def _on_brainstorm(_d: Any) -> None:
                    _on_stage({"stage": "brainstorm"})

                def _on_distill(_d: Any) -> None:
                    _on_stage({"stage": "distill"})

                def _on_flex(_d: Any) -> None:
                    _on_stage({"stage": "flex"})

                def _on_worker(data: Any) -> None:
                    # Prefer concrete worker id so UI pulses only that card
                    wid = ""
                    if isinstance(data, dict):
                        wid = str(data.get("worker") or "").strip()
                    _on_stage({"stage": wid if wid else "work"})

                def _cleanup_handlers() -> None:
                    self.bus.off("pipeline.stage", _on_stage)
                    self.bus.off("pipeline.brainstorm", _on_brainstorm)
                    self.bus.off("pipeline.distill", _on_distill)
                    self.bus.off("pipeline.flex", _on_flex)
                    self.bus.off("pipeline.worker", _on_worker)

                try:
                    if job.get("cancel"):
                        _finalize_job("cancelled")
                        job["snapshot"] = self.snapshot()
                        return
                    self._active_job_id = job_id
                    job["stage"] = "running"
                    # Handlers only while this job owns the pipeline lock
                    self.bus.on("pipeline.stage", _on_stage)
                    self.bus.on("pipeline.brainstorm", _on_brainstorm)
                    self.bus.on("pipeline.distill", _on_distill)
                    self.bus.on("pipeline.flex", _on_flex)
                    self.bus.on("pipeline.worker", _on_worker)
                    handlers_on = True
                    # Cooperative soft-cancel between stages/workers
                    self.pipeline.cancel_check = lambda: bool(job.get("cancel"))
                    try:
                        runner()
                    finally:
                        self.pipeline.cancel_check = None
                    _finalize_job(self.pipeline.state.stage.value)
                    if not job.get("stage"):
                        job["stage"] = self.pipeline.state.stage.value
                    job["snapshot"] = self.snapshot()
                except Exception as exc:  # noqa: BLE001
                    # PipelineCancelled is a subclass of Exception — treat as cancel
                    from gnom_hub.pipeline.orchestrator import PipelineCancelled

                    if job.get("cancel") or isinstance(exc, PipelineCancelled):
                        job["cancel"] = True
                        _finalize_job("cancelled")
                    else:
                        job["status"] = "error"
                        job["error"] = str(exc)
                        job["stage"] = "error"
                        self.last_error = str(exc)
                    try:
                        job["snapshot"] = self.snapshot()
                    except Exception:  # noqa: BLE001
                        pass
                finally:
                    try:
                        self.pipeline.cancel_check = None
                    except Exception:  # noqa: BLE001
                        pass
                    if handlers_on:
                        _cleanup_handlers()
                    if getattr(self, "_active_job_id", None) == job_id:
                        self._active_job_id = None

        t = threading.Thread(target=_run, name=f"{name}-{job_id}", daemon=True)
        t.start()
        return {
            "job_id": job_id,
            "status": "running",
            "stage": "queued",
            "message": f"{name} started — poll /api/jobs/{{id}}",
        }

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

    def chat_async(self, text: str, *, full: bool = False) -> dict[str, Any]:
        """Async: brainstorm turn by default; full=True runs entire pipeline."""
        self.memory.set_query_hint(text)

        def _runner() -> None:
            if full:
                self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
                self.pipeline.start(text)
            else:
                self.pipeline.brainstorm_turn(text)

        return self._start_job("brainstorm" if not full else "pipeline", _runner)

    def execute_async(self) -> dict[str, Any]:
        """Async execute after brainstorm."""

        def _runner() -> None:
            self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
            self.pipeline.execute()

        return self._start_job("execute", _runner)

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

    def rerun_worker_async(self, worker_id: str) -> dict[str, Any]:
        wid = worker_id

        def _runner() -> None:
            self.pipeline.rerun_worker(wid)

        return self._start_job("worker_rerun", _runner)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        jobs = getattr(self, "_jobs", {})
        job = jobs.get(job_id)
        if not job:
            return None
        out = {
            "id": job["id"],
            "name": job.get("name"),
            "status": job["status"],
            "stage": job.get("stage"),
            "error": job.get("error"),
            "started_at": job.get("started_at") or "",
        }
        if job.get("snapshot"):
            out["snapshot"] = job["snapshot"]
        elif job.get("status") in ("running", "queued") and job.get("stage") in (
            "queued",
            "idle",
            "running",
        ):
            # Do not leak another job's live pipeline into a queued job poll
            out["snapshot"] = None
        else:
            out["snapshot"] = self.snapshot()
        return out

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Soft-cancel: mark job cancelled (running thread may still finish)."""
        jobs = getattr(self, "_jobs", {})
        job = jobs.get(job_id)
        if not job:
            raise FileNotFoundError("unknown job")
        if job.get("status") in ("running", "queued") or job.get("stage") == "queued":
            job["cancel"] = True
            job["status"] = "cancelled"
            job["error"] = "cancelled by user"
            job["stage"] = "cancelled"
            self._append_trace("job.cancel", {"id": job_id})
        return {
            "id": job["id"],
            "name": job.get("name"),
            "status": job["status"],
            "stage": job.get("stage"),
            "error": job.get("error"),
        }

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recent jobs (newest first), without heavy snapshots."""
        jobs = getattr(self, "_jobs", {})
        rows: list[dict[str, Any]] = []
        for j in jobs.values():
            if not isinstance(j, dict):
                continue
            rows.append(
                {
                    "id": j.get("id"),
                    "name": j.get("name") or "job",
                    "status": j.get("status"),
                    "stage": j.get("stage"),
                    "error": j.get("error"),
                    "started_at": j.get("started_at") or "",
                }
            )
        rows.sort(key=lambda r: str(r.get("started_at") or r.get("id") or ""), reverse=True)
        return rows[: max(1, min(50, int(limit)))]

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

    def clarify_async(self, option: str) -> dict[str, Any]:
        """Async clarify under the same pipeline lock as chat/execute."""
        opt = option

        def _runner() -> None:
            self.pipeline.answer_clarify(opt)

        return self._start_job("clarify", _runner)

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

    def save_checkpoint(self) -> dict[str, Any]:
        """Persist pipeline state for resume (plan §8.1 light checkpoint)."""
        st = self.pipeline.state
        payload = {
            "version": 1,
            "stage": st.stage.value,
            "mode": st.mode,
            "user_text": st.user_text,
            "memory_context": st.memory_context,
            "brainstorm_notes": st.brainstorm_notes,
            "brainstorm_turns": list(st.brainstorm_turns or []),
            "distilled_requirements": list(st.distilled_requirements),
            "flex_notes": st.flex_notes,
            "worker_results": list(st.worker_results),
            "worker_outputs": list(st.worker_outputs or []),
            "quality_notes": st.quality_notes,
            "warnings": list(st.warnings),
            "error": st.error,
            "pending_question": (
                {
                    "id": st.pending_question.id,
                    "text": st.pending_question.text,
                    "options": list(st.pending_question.options),
                }
                if st.pending_question
                else None
            ),
        }
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self._checkpoint_path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )
        self._append_trace("checkpoint.save", {"path": str(self._checkpoint_path)})
        return {"ok": True, "path": str(self._checkpoint_path)}

    def load_checkpoint(self) -> dict[str, Any]:
        """Restore pipeline state from checkpoint file."""
        from gnom_hub.pipeline.models import DistillQuestion, PipelineStage, PipelineState

        path = self._checkpoint_path
        if not path.is_file():
            raise FileNotFoundError("no checkpoint")
        data = json.loads(path.read_text(encoding="utf-8"))
        q = None
        pq = data.get("pending_question")
        if isinstance(pq, dict) and pq.get("text"):
            q = DistillQuestion(
                id=str(pq.get("id") or "q1"),
                text=str(pq["text"]),
                options=list(pq.get("options") or ["Yes", "No", "Whatever", "Later"]),
            )
        stage_raw = str(data.get("stage") or "idle")
        try:
            stage = PipelineStage(stage_raw)
        except ValueError:
            stage = PipelineStage.idle
        self.pipeline._state = PipelineState(
            stage=stage,
            user_text=str(data.get("user_text") or ""),
            memory_context=str(data.get("memory_context") or ""),
            brainstorm_notes=str(data.get("brainstorm_notes") or ""),
            brainstorm_turns=list(data.get("brainstorm_turns") or []),
            mode=str(data.get("mode") or "brainstorm"),
            distilled_requirements=list(data.get("distilled_requirements") or []),
            flex_notes=str(data.get("flex_notes") or ""),
            pending_question=q,
            worker_results=list(data.get("worker_results") or []),
            worker_outputs=list(data.get("worker_outputs") or []),
            quality_notes=str(data.get("quality_notes") or ""),
            warnings=list(data.get("warnings") or []),
            error=data.get("error"),
        )
        self._append_trace("checkpoint.load", {"stage": stage.value})
        return self.snapshot()

    def save(self) -> dict[str, Any]:
        self.hot.save()
        self.warm.save()
        agents_path = self._save_agent_state()
        return {
            "ok": True,
            "path": str(self.hot.session_path),
            "warm_path": str(self.warm.facts_path),
            "agents_path": str(agents_path),
            "summary": self.hot.get_context_summary(),
            "warm_facts": len(self.warm.all_facts()),
            "canvas_nodes": len(self.hot.canvas.nodes),
        }

    def reset_session(
        self,
        *,
        keep_agents: bool = True,
        clear_warm: bool = False,
        archive: bool = True,
    ) -> dict[str, Any]:
        """Clear HOT session + pipeline. Optionally archive to COLD first. WARM kept unless clear_warm."""
        # Soft-cancel any in-flight jobs so they cannot overwrite a fresh pipeline
        cancelled_jobs = 0
        jobs = getattr(self, "_jobs", None)
        if not isinstance(jobs, dict):
            jobs = {}
            self._jobs = jobs
        for jid, job in list(jobs.items()):
            if isinstance(job, dict) and job.get("status") in ("running", "queued"):
                job["cancel"] = True
                job["status"] = "cancelled"
                job["error"] = job.get("error") or "cancelled by reset"
                job["stage"] = "cancelled"
                cancelled_jobs += 1
                _ = jid
        self._active_job_id = None

        archived = None
        with self._pipeline_lock_obj():
            if archive and (self.hot.session.get("messages") or self.hot.session.get("facts")):
                archived = self.archive_cold(label="auto-reset")
            self.hot.clear(save=True)
            if clear_warm:
                self.warm.clear()
            if not keep_agents:
                self.agents = AgentManager(self.bus)
                self.agents.on_start()
            self.pipeline = self._new_pipeline()
            self.last_error = None
            # Drop light checkpoint so restore cannot re-inject old brainstorm
            if self._checkpoint_path.is_file():
                try:
                    self._checkpoint_path.unlink()
                except OSError:
                    pass
            snap = self.snapshot()
        if archived:
            snap["archived"] = archived
        if cancelled_jobs:
            snap["cancelled_jobs"] = cancelled_jobs
        return snap

    def telegram_start(self) -> dict[str, Any]:
        ok = self.telegram.start()
        return {"ok": ok, "running": self.telegram.running, "configured": self.telegram.enabled}

    def telegram_stop(self) -> dict[str, Any]:
        self.telegram.stop()
        return {"ok": True, "running": False}

    def telegram_inbound(self, text: str, chat_id: int | None = None) -> dict[str, Any]:
        reply = self.telegram.handle_text(text, chat_id)
        return {"reply": reply, "snapshot": self.snapshot()}

    def clean_state(self) -> dict[str, Any]:
        """
        One-click clean state (plan §7): clear HOT + temp workspace + pipeline,
        keep WARM long-term memory and agent toggles.
        """
        jobs = getattr(self, "_jobs", None)
        if not isinstance(jobs, dict):
            jobs = {}
            self._jobs = jobs
        for job in list(jobs.values()):
            if isinstance(job, dict) and job.get("status") in ("running", "queued"):
                job["cancel"] = True
                job["status"] = "cancelled"
                job["error"] = job.get("error") or "cancelled by clean"
                job["stage"] = "cancelled"
        self._active_job_id = None
        archived = None
        with self._pipeline_lock_obj():
            if self.hot.session.get("messages") or self.hot.session.get("facts"):
                archived = self.archive_cold(label="clean-state")
            self.hot.clear(save=True)
            removed = self.workspace.clear_temp()
            self.pipeline = self._new_pipeline()
            self.last_error = None
            self.trace = []
            if self._checkpoint_path.is_file():
                try:
                    self._checkpoint_path.unlink()
                except OSError:
                    pass
            snap = self.snapshot()
        # Clean is a hard wipe — drop pinned export too
        self._last_execute_export = None
        snap["clean"] = {
            "ok": True,
            "temp_removed": removed,
            "archived": archived,
            "warm_kept": True,
        }
        return snap

    def create_backup(self) -> dict[str, Any]:
        """Zip HOT + WARM + agents + checkpoint into data/backups/."""
        import zipfile
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = self.root / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        path = backup_dir / f"gnom-hub-backup-{stamp}.zip"
        # Ensure current state on disk
        self.hot.save()
        self.warm.save()
        self._save_agent_state()
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for folder in ("hot", "warm"):
                base = self.root / "data" / folder
                if not base.is_dir():
                    continue
                for f in base.rglob("*"):
                    if f.is_file():
                        zf.write(f, arcname=str(f.relative_to(self.root / "data")))
        self._append_trace("backup.create", {"path": str(path)})
        return {"ok": True, "path": str(path), "bytes": path.stat().st_size}

    def list_backups(self) -> list[dict[str, Any]]:
        backup_dir = self.root / "data" / "backups"
        if not backup_dir.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for p in sorted(backup_dir.glob("gnom-hub-backup-*.zip"), reverse=True):
            try:
                out.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "bytes": p.stat().st_size,
                    }
                )
            except OSError:
                continue
        return out[:30]

    def backup_path(self, name: str) -> Path:
        """Safe path under data/backups for download."""
        safe = Path(name).name
        if not safe.startswith("gnom-hub-backup-") or not safe.endswith(".zip"):
            raise ValueError("invalid backup name")
        path = (self.root / "data" / "backups" / safe).resolve()
        base = (self.root / "data" / "backups").resolve()
        if not str(path).startswith(str(base)) or not path.is_file():
            raise FileNotFoundError(safe)
        return path

    def delete_backup(self, name: str) -> dict[str, Any]:
        path = self.backup_path(name)
        path.unlink()
        self._append_trace("backup.delete", {"name": path.name})
        return {"ok": True, "deleted": path.name, "backups": self.list_backups()}

    def restore_backup(
        self,
        name: str,
        *,
        archive_current: bool = True,
        load_checkpoint: bool = True,
    ) -> dict[str, Any]:
        """Extract backup zip into data/hot + data/warm and reload memory/agents."""
        import shutil
        import tempfile
        import zipfile

        path = self.backup_path(name)
        archived = None
        if archive_current:
            sess = self.hot.session or {}
            if sess.get("messages") or sess.get("facts"):
                archived = self.archive_cold(label="pre-backup-restore").get("archive")

        data_root = (self.root / "data").resolve()
        with tempfile.TemporaryDirectory(prefix="gnom-backup-") as td:
            tdp = Path(td)
            with zipfile.ZipFile(path, "r") as zf:
                # zip-slip safe extract
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    # only hot/ and warm/ members
                    name_in = info.filename.replace(chr(92), "/").lstrip("/")
                    if ".." in name_in.split("/"):
                        continue
                    top = name_in.split("/", 1)[0]
                    if top not in ("hot", "warm"):
                        continue
                    dest = (tdp / name_in).resolve()
                    if not str(dest).startswith(str(tdp.resolve())):
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, dest.open("wb") as out:
                        shutil.copyfileobj(src, out)

            for folder in ("hot", "warm"):
                src_dir = tdp / folder
                if not src_dir.is_dir():
                    continue
                dest_dir = data_root / folder
                dest_dir.mkdir(parents=True, exist_ok=True)
                for f in src_dir.rglob("*"):
                    if not f.is_file():
                        continue
                    rel = f.relative_to(src_dir)
                    target = (dest_dir / rel).resolve()
                    if not str(target).startswith(str(dest_dir.resolve())):
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)

        self.hot.load()
        self.warm.load()
        self._load_agent_state()
        ckpt_loaded = False
        if load_checkpoint and self._checkpoint_path.is_file():
            try:
                self.load_checkpoint()
                ckpt_loaded = True
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                ckpt_loaded = False

        self._append_trace(
            "backup.restore",
            {
                "name": path.name,
                "checkpoint": ckpt_loaded,
                "archived_previous": bool(archived),
            },
        )
        snap = self.snapshot()
        snap["ok"] = True
        snap["restored_backup"] = path.name
        snap["checkpoint_loaded"] = ckpt_loaded
        if archived:
            snap["archived_previous"] = archived
        return snap

    def delete_worker_preset(self, name: str) -> dict[str, Any]:
        presets = [p for p in self.list_worker_presets() if p.get("name") != name]
        self._presets_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self._presets_path,
            json.dumps({"presets": presets}, ensure_ascii=False, indent=2) + "\n",
        )
        return {"ok": True, "presets": presets}

    def list_worker_presets(self) -> list[dict[str, Any]]:
        path = self._presets_path
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(data, list):
            return data
        return list(data.get("presets") or [])

    def save_worker_preset(self, name: str, agent_id: str = "worker1") -> dict[str, Any]:
        """Save current worker tuning as a named preset (plan: reusable workers)."""
        agent = self.agents.get(agent_id)
        presets = self.list_worker_presets()
        entry = {
            "name": name.strip() or f"preset-{agent_id}",
            "source_agent": agent.id.value,
            "system_prompt": agent.system_prompt or "",
            "model": agent.model,
            "temperature": agent.temperature,
            "top_p": agent.top_p,
            "max_tokens": agent.max_tokens,
            "frequency_penalty": agent.frequency_penalty,
            "presence_penalty": agent.presence_penalty,
        }
        presets = [p for p in presets if p.get("name") != entry["name"]]
        presets.append(entry)
        self._presets_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self._presets_path,
            json.dumps({"presets": presets}, ensure_ascii=False, indent=2) + "\n",
        )
        return {"ok": True, "preset": entry, "presets": presets}

    def apply_worker_preset(self, name: str, agent_id: str = "worker1") -> dict[str, Any]:
        presets = self.list_worker_presets()
        match = next((p for p in presets if p.get("name") == name), None)
        if not match:
            raise ValueError(f"Unknown preset: {name!r}")
        return self.set_agent_tune(
            agent_id,
            {
                "system_prompt": match.get("system_prompt"),
                "model": match.get("model"),
                "temperature": match.get("temperature"),
                "top_p": match.get("top_p"),
                "max_tokens": match.get("max_tokens"),
                "frequency_penalty": match.get("frequency_penalty"),
                "presence_penalty": match.get("presence_penalty"),
            },
        )

    # ── team presets (who is on + flex + plan_mode + worker tunes) ──

    PLAN_MODES: tuple[str, ...] = ("default", "full_page_html", "plan_qa", "diagnosis")

    def list_team_presets(self) -> list[dict[str, Any]]:
        path = self._team_presets_path
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict)]
        return [p for p in (data.get("presets") or []) if isinstance(p, dict)]

    def _write_team_presets(self, presets: list[dict[str, Any]]) -> None:
        self._team_presets_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self._team_presets_path,
            json.dumps({"presets": presets}, ensure_ascii=False, indent=2) + "\n",
        )

    def save_team_preset(self, name: str) -> dict[str, Any]:
        """Snapshot current enables, flex, plan_mode, and worker tunes."""
        key = (name or "").strip() or "team"
        enabled: dict[str, bool] = {}
        tunes: dict[str, dict[str, Any]] = {}
        for a in self.agents.list_agents():
            aid = a.id.value
            enabled[aid] = bool(a.enabled)
            if aid.startswith("worker"):
                tunes[aid] = {
                    "system_prompt": a.system_prompt or "",
                    "model": a.model,
                    "temperature": a.temperature,
                    "top_p": a.top_p,
                    "max_tokens": a.max_tokens,
                    "frequency_penalty": a.frequency_penalty,
                    "presence_penalty": a.presence_penalty,
                }
        flex = self.agents.get(AgentId.FLEX)
        entry = {
            "name": key,
            "flex": (flex.preset or "security"),
            "plan_mode": getattr(self, "plan_mode", "default") or "default",
            "enabled": enabled,
            "tunes": tunes,
        }
        presets = [p for p in self.list_team_presets() if p.get("name") != key]
        presets.append(entry)
        self._write_team_presets(presets)
        return {"ok": True, "preset": entry, "presets": presets}

    def apply_team_preset(self, name: str) -> dict[str, Any]:
        key = (name or "").strip()
        match = next((p for p in self.list_team_presets() if p.get("name") == key), None)
        if not match:
            raise ValueError(f"Unknown team preset: {name!r}")

        enabled = match.get("enabled") or {}
        if isinstance(enabled, dict):
            for a in self.agents.list_agents():
                aid = a.id.value
                if not a.toggleable:
                    a.enabled = True
                    continue
                if aid in enabled:
                    a.enabled = bool(enabled[aid])
                self.agents.emit_status(a.id)

        flex_name = str(match.get("flex") or "security")
        try:
            self.agents.set_flex_preset(flex_name)
        except ValueError:
            pass

        mode = str(match.get("plan_mode") or "default").strip().lower()
        if mode not in self.PLAN_MODES:
            mode = "default"
        self.plan_mode = mode
        self.pipeline.plan_mode = mode

        tunes = match.get("tunes") or {}
        if isinstance(tunes, dict):
            for aid, fields in tunes.items():
                if not isinstance(fields, dict) or not str(aid).startswith("worker"):
                    continue
                try:
                    self.set_agent_tune(str(aid), fields)
                except (KeyError, TypeError, ValueError):
                    pass

        self._save_agent_state()
        return {
            "ok": True,
            "name": key,
            "plan_mode": self.plan_mode,
            "agents": [self._agent_dict(a) for a in self.agents.list_agents()],
            "snapshot": self.snapshot(),
        }

    def delete_team_preset(self, name: str) -> dict[str, Any]:
        key = (name or "").strip()
        presets = [p for p in self.list_team_presets() if p.get("name") != key]
        self._write_team_presets(presets)
        return {"ok": True, "presets": presets}

    def set_plan_mode(self, mode: str) -> dict[str, Any]:
        key = (mode or "default").strip().lower()
        if key not in self.PLAN_MODES:
            raise ValueError(f"Unknown plan_mode: {mode!r}. Allowed: {self.PLAN_MODES}")
        self.plan_mode = key
        self.pipeline.plan_mode = key
        return {"ok": True, "plan_mode": key}

    @staticmethod
    def _sanitize_ui_chat_log(raw: Any) -> list[dict[str, str]]:
        """Cap chat lines for pack portability."""
        if not isinstance(raw, list):
            return []
        out: list[dict[str, str]] = []
        for item in raw[-80:]:
            if isinstance(item, str):
                text = item.strip()[:4000]
                if text:
                    out.append({"who": "system", "text": text, "ts": ""})
                continue
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()[:4000]
            if not text:
                continue
            out.append(
                {
                    "who": str(item.get("who") or "system")[:40],
                    "text": text,
                    "ts": str(item.get("ts") or "")[:32],
                }
            )
        return out

    @staticmethod
    def _sanitize_ui_result_history(raw: Any) -> list[dict[str, Any]]:
        """Cap result-history entries for pack portability."""
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw[:12]:
            if not isinstance(item, dict):
                continue
            outputs: list[dict[str, Any]] = []
            for o in (item.get("outputs") or [])[:8]:
                if not isinstance(o, dict):
                    continue
                outputs.append(
                    {
                        "worker": str(o.get("worker") or "")[:40],
                        "name": str(o.get("name") or "")[:80],
                        "task": str(o.get("task") or "")[:2000],
                        "result": str(o.get("result") or "")[:50000],
                        "index": o.get("index"),
                    }
                )
            turns: list[dict[str, str]] = []
            for tr in (item.get("brainstorm_turns") or [])[:40]:
                if not isinstance(tr, dict):
                    continue
                turns.append(
                    {
                        "role": str(tr.get("role") or "")[:40],
                        "text": str(tr.get("text") or "")[:4000],
                    }
                )
            out.append(
                {
                    "id": str(item.get("id") or "")[:40],
                    "ts": str(item.get("ts") or "")[:40],
                    "label": str(item.get("label") or "")[:80],
                    "user_text": str(item.get("user_text") or "")[:4000],
                    "brainstorm_notes": str(item.get("brainstorm_notes") or "")[:20000],
                    "brainstorm_turns": turns,
                    "can_reexec": bool(item.get("can_reexec")),
                    "outputs": outputs,
                }
            )
        return out

    def _collect_workspace_for_pack(
        self,
        *,
        max_files_per_zone: int = 20,
        max_chars_per_file: int = 100_000,
        max_total_chars: int = 500_000,
    ) -> dict[str, list[dict[str, str]]]:
        """Read temp/perm text files for pack (size-capped)."""
        out: dict[str, list[dict[str, str]]] = {"temp": [], "perm": []}
        total = 0
        for zone in ("temp", "perm"):
            try:
                files = self.workspace.list_files(zone)
            except OSError:
                continue
            for meta in files[:max_files_per_zone]:
                if total >= max_total_chars:
                    break
                name = str(meta.get("name") or "")
                if not name:
                    continue
                try:
                    # read full then cap (read_text already caps with ellipsis)
                    text = self.workspace.read_text(zone, name, max_chars=max_chars_per_file)
                except (OSError, FileNotFoundError, ValueError):
                    continue
                if total + len(text) > max_total_chars:
                    remain = max_total_chars - total
                    if remain < 64:
                        break
                    text = text[: remain - 1] + "…"
                out[zone].append({"name": name, "content": text})
                total += len(text)
        return out

    def _restore_workspace_from_pack(self, raw: Any) -> dict[str, int]:
        """Write pack workspace files into temp/perm. Returns counts."""
        if not isinstance(raw, dict):
            return {"temp": 0, "perm": 0}
        counts = {"temp": 0, "perm": 0}
        for zone in ("temp", "perm"):
            items = raw.get(zone)
            if not isinstance(items, list):
                continue
            for item in items[:20]:
                if not isinstance(item, dict):
                    continue
                name = Path(str(item.get("name") or "")).name
                content = item.get("content")
                if not name or content is None:
                    continue
                text = str(content)[:100_000]
                try:
                    self.workspace.write_text(zone, name, text)
                    counts[zone] += 1
                except (OSError, ValueError):
                    continue
        return counts

    @staticmethod
    def _sanitize_ui_prefs(raw: Any) -> dict[str, Any]:
        """compact + ui_lang only."""
        if not isinstance(raw, dict):
            return {}
        out: dict[str, Any] = {}
        if "compact" in raw:
            out["compact"] = bool(raw.get("compact"))
        lang = str(raw.get("ui_lang") or "").strip().lower()
        if lang in ("en", "de"):
            out["ui_lang"] = lang
        return out

    def export_session_pack(
        self,
        label: str | None = None,
        *,
        persist: bool = True,
        ui_chat_log: list | None = None,
        ui_result_history: list | None = None,
        include_workspace: bool = True,
        ui_prefs: dict | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Portable JSON pack: HOT + WARM + agents + pipeline + workspace (+ UI)."""
        from datetime import datetime, timezone

        self.hot.save()
        self.warm.save()
        agents_path = self._save_agent_state()
        agents_payload: dict[str, Any] = {"agents": []}
        try:
            agents_payload = json.loads(agents_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            agents_payload = {
                "agents": [
                    {
                        "id": a.id.value,
                        "enabled": a.enabled,
                        "preset": a.preset,
                        "model": a.model,
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
        st = self.pipeline.state
        pipeline = {
            "stage": st.stage.value,
            "mode": st.mode,
            "user_text": st.user_text,
            "memory_context": st.memory_context,
            "brainstorm_notes": st.brainstorm_notes,
            "brainstorm_turns": list(st.brainstorm_turns or []),
            "distilled_requirements": list(st.distilled_requirements),
            "flex_notes": st.flex_notes,
            "worker_results": list(st.worker_results),
            "worker_outputs": list(st.worker_outputs or []),
            "quality_notes": getattr(st, "quality_notes", "") or "",
            "warnings": list(st.warnings),
            "error": st.error,
            "pending_question": (
                {
                    "id": st.pending_question.id,
                    "text": st.pending_question.text,
                    "options": list(st.pending_question.options),
                }
                if st.pending_question
                else None
            ),
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pack_label = (label or st.user_text or "session").strip()[:80] or "session"
        pack = {
            "format": "gnom-hub-session-pack",
            "format_version": 1,
            "app_version": "3.7.1",
            "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "label": pack_label,
            "notes": (str(notes).strip()[:200] if notes else ""),
            "hot": dict(self.hot.session),
            "canvas_mmd": self.hot.canvas.to_mermaid(),
            "warm_facts": self.warm.all_facts(),
            "agents": agents_payload.get("agents") or [],
            "pipeline": pipeline,
        }
        if ui_chat_log is not None:
            pack["ui_chat_log"] = self._sanitize_ui_chat_log(ui_chat_log)
        if ui_result_history is not None:
            pack["ui_result_history"] = self._sanitize_ui_result_history(ui_result_history)
        if include_workspace:
            pack["workspace"] = self._collect_workspace_for_pack()
        # Always embed server ui_lang; merge client prefs when provided
        prefs = {"ui_lang": self.ui_lang if self.ui_lang in ("en", "de") else "en"}
        if ui_prefs is not None:
            prefs.update(self._sanitize_ui_prefs(ui_prefs))
        pack["ui_prefs"] = prefs
        filename = f"gnom-hub-session-{stamp}.json"
        saved_path: str | None = None
        pruned: list[str] = []
        if persist:
            self._packs_dir.mkdir(parents=True, exist_ok=True)
            path = self._packs_dir / filename
            atomic_write_text(path, json.dumps(pack, ensure_ascii=False, indent=2) + "\n")
            saved_path = str(path)
            pruned = self.prune_session_packs()
        self._append_trace(
            "session.pack.export",
            {"label": pack["label"], "path": saved_path or "", "pruned": len(pruned)},
        )
        return {
            "ok": True,
            "filename": filename,
            "path": saved_path,
            "pack": pack,
            "chars": len(json.dumps(pack, ensure_ascii=False)),
            "packs": self.list_session_packs()[:12],
            "pruned": pruned,
        }

    def prune_session_packs(self, max_keep: int | None = None) -> list[str]:
        """Delete oldest packs beyond max_keep (default: self.pack_max). Newest first by name."""
        keep = self.pack_max if max_keep is None else int(max_keep)
        keep = max(5, min(100, keep))
        if not self._packs_dir.is_dir():
            return []
        files = sorted(self._packs_dir.glob("gnom-hub-session-*.json"), reverse=True)
        deleted: list[str] = []
        for p in files[keep:]:
            try:
                p.unlink()
                deleted.append(p.name)
            except OSError:
                continue
        if deleted:
            self._append_trace(
                "session.pack.prune",
                {"deleted": len(deleted), "keep": keep},
            )
        return deleted

    def store_session_pack(
        self,
        pack: dict[str, Any],
        *,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Write a pack JSON under data/packs/ (e.g. after USB import)."""
        if not isinstance(pack, dict):
            raise TypeError("pack must be an object")
        if pack.get("format") != "gnom-hub-session-pack":
            raise ValueError("not a gnom-hub-session-pack")
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = Path(filename or f"gnom-hub-session-{stamp}.json").name
        if not name.startswith("gnom-hub-session-") or not name.endswith(".json"):
            name = f"gnom-hub-session-{stamp}.json"
        self._packs_dir.mkdir(parents=True, exist_ok=True)
        path = self._packs_dir / name
        atomic_write_text(path, json.dumps(pack, ensure_ascii=False, indent=2) + "\n")
        pruned = self.prune_session_packs()
        self._append_trace("session.pack.store", {"name": path.name})
        return {
            "ok": True,
            "name": path.name,
            "path": str(path),
            "pruned": pruned,
            "packs": self.list_session_packs()[:12],
        }

    def list_session_packs(self) -> list[dict[str, Any]]:
        """List packs under data/packs/ (newest first)."""
        from datetime import datetime, timezone

        if not self._packs_dir.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for p in sorted(self._packs_dir.glob("gnom-hub-session-*.json"), reverse=True):
            try:
                label = p.stem
                exported_at = ""
                notes = ""
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        if data.get("label"):
                            label = str(data["label"])[:80]
                        exported_at = str(data.get("exported_at") or "")
                        notes = str(data.get("notes") or "")[:200]
                except (OSError, json.JSONDecodeError):
                    pass
                st = p.stat()
                mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                out.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "bytes": st.st_size,
                        "label": label,
                        "notes": notes,
                        "exported_at": exported_at,
                        "mtime": mtime.replace(microsecond=0).isoformat(),
                    }
                )
            except OSError:
                continue
        return out[:30]

    def _pack_path(self, name: str) -> Path:
        safe = Path(name).name
        if not safe.startswith("gnom-hub-session-") or not safe.endswith(".json"):
            raise ValueError("invalid pack name")
        path = (self._packs_dir / safe).resolve()
        base = self._packs_dir.resolve()
        if not str(path).startswith(str(base)) or not path.is_file():
            raise FileNotFoundError(safe)
        return path

    def load_session_pack_file(self, name: str) -> dict[str, Any]:
        """Load pack JSON from data/packs/{name} (does not import)."""
        path = self._pack_path(name)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("pack file is not an object")
        return {"ok": True, "name": path.name, "pack": data}

    def import_session_pack_file(
        self,
        name: str,
        *,
        include_warm: bool = True,
        include_agents: bool = True,
    ) -> dict[str, Any]:
        """Import a pack stored under data/packs/."""
        data = self.load_session_pack_file(name)
        return self.import_session_pack(
            data["pack"],
            include_warm=include_warm,
            include_agents=include_agents,
        )

    def rename_session_pack(
        self,
        name: str,
        label: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Update label and/or notes inside a stored pack (filename unchanged)."""
        path = self._pack_path(name)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("pack file is not an object")
        if data.get("format") != "gnom-hub-session-pack":
            raise ValueError("not a gnom-hub-session-pack")
        if label is None and notes is None:
            raise ValueError("label or notes required")
        if label is not None:
            new_label = (label or "").strip()[:80]
            if not new_label:
                raise ValueError("label required")
            data["label"] = new_label
        if notes is not None:
            data["notes"] = str(notes).strip()[:200]
        atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        self._append_trace(
            "session.pack.rename",
            {
                "name": path.name,
                "label": data.get("label"),
                "notes": bool(data.get("notes")),
            },
        )
        return {
            "ok": True,
            "name": path.name,
            "label": data.get("label"),
            "notes": data.get("notes") or "",
            "packs": self.list_session_packs(),
        }

    def delete_session_pack(self, name: str) -> dict[str, Any]:
        path = self._pack_path(name)
        path.unlink()
        self._append_trace("session.pack.delete", {"name": path.name})
        return {"ok": True, "deleted": path.name, "packs": self.list_session_packs()}

    def maybe_auto_pack(self) -> dict[str, Any] | None:
        """If auto_pack is on, persist a pack after successful Execute."""
        if not self.auto_pack_after_execute:
            return None
        try:
            return self.export_session_pack(persist=True)
        except Exception as exc:  # noqa: BLE001
            self._append_trace("session.pack.auto_fail", {"error": str(exc)})
            return None

    def import_session_pack(
        self,
        pack: dict[str, Any],
        *,
        include_warm: bool = True,
        include_agents: bool = True,
        store: bool = False,
    ) -> dict[str, Any]:
        """Restore a portable session pack into this hub."""
        from gnom_hub.pipeline.models import DistillQuestion, PipelineStage, PipelineState

        if not isinstance(pack, dict):
            raise TypeError("pack must be an object")
        if pack.get("format") != "gnom-hub-session-pack":
            raise ValueError("not a gnom-hub-session-pack")
        if store:
            self.store_session_pack(pack)
        hot = pack.get("hot") if isinstance(pack.get("hot"), dict) else {}
        self.hot.session = {
            "messages": list(hot.get("messages") or []),
            "facts": list(hot.get("facts") or []),
            "updated_at": hot.get("updated_at") or "",
        }
        canvas_mmd = str(pack.get("canvas_mmd") or "")
        if canvas_mmd.strip():
            self.hot.canvas_path.parent.mkdir(parents=True, exist_ok=True)
            if not canvas_mmd.endswith("\n"):
                canvas_mmd = canvas_mmd + "\n"
            atomic_write_text(self.hot.canvas_path, canvas_mmd)
            self.hot.canvas.load(self.hot.canvas_path)
        else:
            self.hot.canvas.clear()
        self.hot.save()

        if isinstance(pack.get("workspace"), dict):
            self._restore_workspace_from_pack(pack.get("workspace"))

        if include_warm:
            for fact in pack.get("warm_facts") or []:
                text = str(fact).strip()
                if text:
                    self.warm.add_fact(text)

        if include_agents and isinstance(pack.get("agents"), list):
            for item in pack["agents"]:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                try:
                    agent = self.agents.get(str(item["id"]))
                except ValueError:
                    continue
                if agent.toggleable and "enabled" in item:
                    agent.enabled = bool(item["enabled"])
                if str(getattr(agent.id, "value", agent.id)) == "flex" and item.get("preset"):
                    try:
                        self.agents.set_flex_preset(str(item["preset"]))
                    except ValueError:
                        pass
                if item.get("model"):
                    agent.model = str(item["model"])
                if "tts" in item:
                    agent.tts = bool(item["tts"])
                if item.get("system_prompt") is not None:
                    agent.system_prompt = str(item["system_prompt"]) or None
                for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
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
            self._save_agent_state()

        data = pack.get("pipeline") if isinstance(pack.get("pipeline"), dict) else {}
        q = None
        pq = data.get("pending_question")
        if isinstance(pq, dict) and pq.get("text"):
            q = DistillQuestion(
                id=str(pq.get("id") or "q1"),
                text=str(pq["text"]),
                options=list(pq.get("options") or ["Yes", "No", "Whatever", "Later"]),
            )
        stage_raw = str(data.get("stage") or "brainstorm")
        try:
            stage = PipelineStage(stage_raw)
        except ValueError:
            stage = PipelineStage.brainstorm
        self.pipeline._state = PipelineState(
            stage=stage,
            user_text=str(data.get("user_text") or ""),
            memory_context=str(data.get("memory_context") or ""),
            brainstorm_notes=str(data.get("brainstorm_notes") or ""),
            brainstorm_turns=list(data.get("brainstorm_turns") or []),
            mode=str(data.get("mode") or "brainstorm"),
            distilled_requirements=list(data.get("distilled_requirements") or []),
            flex_notes=str(data.get("flex_notes") or ""),
            pending_question=q,
            worker_results=list(data.get("worker_results") or []),
            worker_outputs=list(data.get("worker_outputs") or []),
            quality_notes=str(data.get("quality_notes") or ""),
            warnings=list(data.get("warnings") or []),
            error=data.get("error"),
        )
        self.last_error = None
        self._append_trace(
            "session.pack.import",
            {"label": pack.get("label"), "stage": stage.value},
        )
        if isinstance(pack.get("ui_prefs"), dict):
            prefs = self._sanitize_ui_prefs(pack.get("ui_prefs"))
            lang = prefs.get("ui_lang")
            if lang in ("en", "de"):
                self.ui_lang = lang
        snap = self.snapshot()
        if "ui_chat_log" in pack:
            snap["ui_chat_log"] = self._sanitize_ui_chat_log(pack.get("ui_chat_log"))
        if "ui_result_history" in pack:
            snap["ui_result_history"] = self._sanitize_ui_result_history(
                pack.get("ui_result_history")
            )
        if isinstance(pack.get("ui_prefs"), dict):
            snap["ui_prefs"] = self._sanitize_ui_prefs(pack.get("ui_prefs"))
        if pack.get("notes") is not None:
            snap["pack_notes"] = str(pack.get("notes") or "")[:200]
        return snap

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
