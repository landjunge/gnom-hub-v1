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
from gnom_hub.ui.tooltips import TOOLTIPS


class Hub:
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
        self.telegram = self._init_telegram()
        self._load_agent_state()
        # Core agents + worker1/2 on; worker3/4 stay off until user enables
        self.agents.enable_all(include_extra_workers=False)
        self._wire_memory()
        self._wire_trace()
        self.agents.on_start()
        # Auto-start telegram poll if GNOM_TELEGRAM_POLL=1
        if os.getenv("GNOM_TELEGRAM_POLL", "").strip() in ("1", "true", "yes"):
            self.telegram_start()

    def _new_pipeline(self) -> Pipeline:
        return Pipeline(
            self.bus,
            llm_manager=self.llm,
            agent_manager=self.agents,
            memory=self.memory,
        )

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
            user_text = str(data.get("user_text") or "")
            if user_text:
                self.hot.add_message("user", user_text)
            notes = str(data.get("brainstorm_notes") or "")
            if notes:
                self.hot.add_message("brainstorm", notes)
            flex = str(data.get("flex_notes") or "")
            if flex:
                self.hot.add_message("flex", flex)
            from gnom_hub.agents.roles import _is_garbage_fact

            # HOT: clean requirements only — never store product-hallucinations
            for req in (data.get("requirements") or [])[:5]:
                text = str(req).strip()
                if (
                    8 <= len(text) <= 160
                    and not text.startswith("Flex/")
                    and not _is_garbage_fact(text)
                ):
                    self.hot.add_fact(text)
                    self.vectors.add(text, meta={"source": "requirement"})
            for req in data.get("requirements") or []:
                text = str(req).strip()
                if text.lower().startswith("ziel:") or text.lower().startswith("goal:"):
                    if 8 <= len(text) <= 160 and not _is_garbage_fact(text):
                        self.warm.add_fact(text)
                    break
            # Worker outputs: messages only, not auto-facts (stops echo loops)
            for res in (data.get("results") or [])[:2]:
                snippet = str(res).strip()[:400]
                if snippet and not _is_garbage_fact(snippet):
                    self.hot.add_message("worker", snippet)
            if data.get("user_text"):
                self.hot.add_message("user", str(data.get("user_text"))[:500])
            self.hot.save()

        def on_error(data: Any) -> None:
            if isinstance(data, dict):
                self.last_error = str(data.get("error") or "pipeline error")
            else:
                self.last_error = str(data)

        def on_memory_curated(data: Any) -> None:
            """LLM-extracted durable facts from Memory agent."""
            if not isinstance(data, dict):
                return
            from gnom_hub.agents.roles import _is_garbage_fact

            for fact in data.get("facts") or []:
                text = str(fact).strip()
                if 8 <= len(text) <= 200 and not _is_garbage_fact(text):
                    self.hot.add_fact(text)
                    self.warm.add_fact(text)
                    self.vectors.add(text, meta={"source": "memory_agent"})
            self.hot.save()

        def on_done(_data: Any) -> None:
            # Long-session compression after each successful pipeline finish
            try:
                self.hot.compress_if_needed()
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

    def _telegram_command(self, cmd: str, arg: str, meta: dict[str, Any]) -> str:
        if cmd == "help":
            return (
                "Gnom-Hub Telegram\n"
                "/status — hub state\n"
                "/do <task> — run pipeline\n"
                "/last — last worker results\n"
                "/reset — clear HOT session (WARM kept)\n"
                "/yes /no /whatever /later — clarify\n"
                "Or send plain text as a task."
            )
        if cmd == "status":
            st = self.pipeline.state
            return (
                f"stage={st.stage.value}\n"
                f"agents={sum(1 for a in self.agents.list_agents() if a.enabled)}/6\n"
                f"deepseek={'yes' if self.llm.has_provider('deepseek') else 'no'}\n"
                f"hot={self.hot.get_context_summary()}\n"
                f"warm_facts={len(self.warm.all_facts())}"
            )
        if cmd == "do":
            if not arg.strip():
                return "Usage: /do <task text>"
            # Full pipeline for Telegram one-shot tasks
            snap = self.chat(arg.strip(), full=True)
            p = snap["pipeline"]
            if p["stage"] == "clarify" and p.get("pending_question"):
                q = p["pending_question"]["text"]
                return f"Clarify needed: {q}\nReply /yes /no /whatever /later"
            results = p.get("worker_results") or []
            head = (p.get("brainstorm_notes") or "")[:200]
            return f"stage={p['stage']}\n{head}\n" + "\n".join(results[:3])
        if cmd == "last":
            st = self.pipeline.state
            if not st.worker_results:
                return "No worker results yet."
            return "\n".join(st.worker_results[:5])
        if cmd == "reset":
            self.reset_session(keep_agents=True)
            return "HOT session reset (WARM facts kept)."
        if cmd in ("yes", "no", "whatever", "later"):
            opt = cmd.capitalize() if cmd != "yes" else "Yes"
            if cmd == "no":
                opt = "No"
            if cmd == "whatever":
                opt = "Whatever"
            if cmd == "later":
                opt = "Later"
            try:
                snap = self.clarify(opt)
            except ValueError as e:
                return str(e)
            p = snap["pipeline"]
            return f"stage={p['stage']}\n" + "\n".join((p.get("worker_results") or [])[:3])
        if cmd == "disable" and arg:
            try:
                en = self.agents.toggle(arg.strip().lower())
                return f"{arg} enabled={en}"
            except ValueError as e:
                return str(e)
        return f"Unknown /{cmd}. Try /help"

    # ── agent persistence ───────────────────────────────────────────

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
            "facts": self.hot.recent_facts(12),
            "warm_facts": self.warm.recent_facts(12),
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
            "version": "2.2.0",
            "flex_presets": list(FLEX_PRESETS),
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

    def chat_sync(self, text: str, *, full: bool = False) -> dict[str, Any]:
        self.last_error = None
        self.memory.set_query_hint(text)
        if full:
            self.pipeline.start(text)
        else:
            self.pipeline.brainstorm_turn(text)
        if self.pipeline.state.error:
            self.last_error = self.pipeline.state.error
        elif full and self.pipeline.state.stage.value == "done":
            self._capture_workspace_outputs()
        return self.snapshot()

    def execute_sync(self) -> dict[str, Any]:
        """Run distill → flex → workers from accumulated brainstorm."""
        self.last_error = None
        self.pipeline.execute()
        if self.pipeline.state.error:
            self.last_error = self.pipeline.state.error
        elif self.pipeline.state.stage.value == "done":
            self._capture_workspace_outputs()
            self.maybe_auto_pack()
        return self.snapshot()

    def _start_job(self, name: str, runner: Any) -> dict[str, Any]:
        import threading
        import uuid

        if not hasattr(self, "_jobs"):
            self._jobs: dict[str, dict[str, Any]] = {}
        if not hasattr(self, "_pipeline_lock"):
            self._pipeline_lock = threading.Lock()

        job_id = uuid.uuid4().hex[:12]
        job: dict[str, Any] = {
            "id": job_id,
            "status": "running",
            "stage": "idle",
            "error": None,
            "snapshot": None,
        }
        self._jobs[job_id] = job
        self.last_error = None

        def _on_stage(data: Any) -> None:
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

        def _on_worker(_d: Any) -> None:
            _on_stage({"stage": "work"})

        # Named handlers so we can unsubscribe (no EventBus listener leak)
        self.bus.on("pipeline.stage", _on_stage)
        self.bus.on("pipeline.brainstorm", _on_brainstorm)
        self.bus.on("pipeline.distill", _on_distill)
        self.bus.on("pipeline.flex", _on_flex)
        self.bus.on("pipeline.worker", _on_worker)

        def _cleanup_handlers() -> None:
            self.bus.off("pipeline.stage", _on_stage)
            self.bus.off("pipeline.brainstorm", _on_brainstorm)
            self.bus.off("pipeline.distill", _on_distill)
            self.bus.off("pipeline.flex", _on_flex)
            self.bus.off("pipeline.worker", _on_worker)

        def _run() -> None:
            # Serialize pipeline jobs — shared orchestrator state
            with self._pipeline_lock:
                try:
                    if job.get("cancel"):
                        job["status"] = "cancelled"
                        job["stage"] = "cancelled"
                        job["snapshot"] = self.snapshot()
                        return
                    runner()
                    stage_val = self.pipeline.state.stage.value
                    if job.get("cancel"):
                        job["status"] = "cancelled"
                        job["error"] = job.get("error") or "cancelled by user"
                        job["stage"] = "cancelled"
                    # Classify by stage first — sticky error alone must not fail a done run
                    elif stage_val == "error":
                        self.last_error = self.pipeline.state.error
                        job["status"] = "error"
                        job["error"] = self.pipeline.state.error or "error"
                        job["stage"] = stage_val
                    elif stage_val == "clarify":
                        job["status"] = "clarify"
                        job["stage"] = stage_val
                    else:
                        job["status"] = "done"
                        job["stage"] = stage_val
                        # Plan: agent outputs land in temp workspace first
                        if name in ("execute", "pipeline"):
                            self._capture_workspace_outputs()
                            if name == "execute":
                                self.maybe_auto_pack()
                    if not job.get("stage"):
                        job["stage"] = self.pipeline.state.stage.value
                    job["snapshot"] = self.snapshot()
                except Exception as exc:  # noqa: BLE001
                    job["status"] = "error"
                    job["error"] = str(exc)
                    job["stage"] = "error"
                    self.last_error = str(exc)
                    job["snapshot"] = self.snapshot()
                finally:
                    _cleanup_handlers()

        t = threading.Thread(target=_run, name=f"{name}-{job_id}", daemon=True)
        t.start()
        return {
            "job_id": job_id,
            "status": "running",
            "stage": "idle",
            "message": f"{name} started — poll /api/jobs/{{id}}",
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
                self.pipeline.start(text)
            else:
                self.pipeline.brainstorm_turn(text)

        return self._start_job("brainstorm" if not full else "pipeline", _runner)

    def execute_async(self) -> dict[str, Any]:
        """Async execute after brainstorm."""
        return self._start_job("execute", self.pipeline.execute)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        jobs = getattr(self, "_jobs", {})
        job = jobs.get(job_id)
        if not job:
            return None
        out = {
            "id": job["id"],
            "status": job["status"],
            "stage": job.get("stage"),
            "error": job.get("error"),
        }
        if job.get("snapshot"):
            out["snapshot"] = job["snapshot"]
        else:
            out["snapshot"] = self.snapshot()
        return out

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Soft-cancel: mark job cancelled (running thread may still finish)."""
        jobs = getattr(self, "_jobs", {})
        job = jobs.get(job_id)
        if not job:
            raise FileNotFoundError("unknown job")
        if job.get("status") == "running":
            job["cancel"] = True
            job["status"] = "cancelled"
            job["error"] = "cancelled by user"
            job["stage"] = "cancelled"
            self._append_trace("job.cancel", {"id": job_id})
        return {
            "id": job["id"],
            "status": job["status"],
            "stage": job.get("stage"),
            "error": job.get("error"),
        }

    def clarify(self, option: str) -> dict[str, Any]:
        """Synchronous clarify (also used after async reaches clarify)."""
        self.last_error = None
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
            "version": "2.2.0",
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
        """Clear HOT session. Optionally archive to COLD first. WARM kept unless clear_warm."""
        archived = None
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
        snap = self.snapshot()
        if archived:
            snap["archived"] = archived
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
        archived = None
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

    def export_session_pack(
        self,
        label: str | None = None,
        *,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Portable JSON pack: HOT + WARM + agents + pipeline (USB / machine hop)."""
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
            "app_version": "2.2.0",
            "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "label": pack_label,
            "hot": dict(self.hot.session),
            "canvas_mmd": self.hot.canvas.to_mermaid(),
            "warm_facts": self.warm.all_facts(),
            "agents": agents_payload.get("agents") or [],
            "pipeline": pipeline,
        }
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
        if not self._packs_dir.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for p in sorted(self._packs_dir.glob("gnom-hub-session-*.json"), reverse=True):
            try:
                label = p.stem
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and data.get("label"):
                        label = str(data["label"])[:80]
                except (OSError, json.JSONDecodeError):
                    pass
                out.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "bytes": p.stat().st_size,
                        "label": label,
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
        return self.snapshot()

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
                "8) Auto-save + Box 3 focus after successful Execute. 9) Session packs (Pack ↓/↑, list Load/↓/Del, auto-pack, prune max). 10) History Re-Exec. 11) Import from USB can store into data/packs/."
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
