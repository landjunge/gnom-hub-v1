"""Application hub: wires EventBus, agents, pipeline, memory, LLM, optional Telegram."""

from __future__ import annotations

import os
from typing import Any

from gnom_hub.agent_ops import AgentOpsMixin
from gnom_hub.agents.manager import AgentManager
from gnom_hub.agents.models import FLEX_PRESETS
from gnom_hub.backup_ops import BackupOpsMixin
from gnom_hub.cold_ops import ColdOpsMixin
from gnom_hub.computer_use.workflow import ComputerUseKit
from gnom_hub.config.keys import ensure_env_from_key_txt, load_keys
from gnom_hub.config.paths import project_root
from gnom_hub.core.event_bus import EventBus
from gnom_hub.export_ops import ExportOpsMixin
from gnom_hub.hot_facts import HotFactsMixin
from gnom_hub.jobs import JobsMixin
from gnom_hub.llm.manager import LLMManager
from gnom_hub.memory.cold import ColdArchive
from gnom_hub.memory.facade import MemoryFacade
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.memory.warm import WarmMemory
from gnom_hub.memory.wiring import MemoryWiringMixin
from gnom_hub.memory.workspace import WorkspaceStore
from gnom_hub.pipeline.orchestrator import Orchestrator as Pipeline
from gnom_hub.plugins.loader import PluginLoader
from gnom_hub.plugins.registry import ToolRegistry
from gnom_hub.presets import PresetsMixin
from gnom_hub.security.god_mode import god_mode_from_env
from gnom_hub.session_ops import SessionOpsMixin
from gnom_hub.session_pack import SessionPackMixin
from gnom_hub.system_ops import SystemOpsMixin
from gnom_hub.telegram.bot import TelegramBridge
from gnom_hub.telegram.commands import TelegramCommandMixin
from gnom_hub.tools_ops import ToolsOpsMixin
from gnom_hub.trace_ops import TraceOpsMixin


class Hub(
    TelegramCommandMixin,
    BackupOpsMixin,
    SessionPackMixin,
    JobsMixin,
    MemoryWiringMixin,
    PresetsMixin,
    SessionOpsMixin,
    TraceOpsMixin,
    ColdOpsMixin,
    ExportOpsMixin,
    HotFactsMixin,
    AgentOpsMixin,
    ToolsOpsMixin,
    SystemOpsMixin,
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

    def clarify(self, option: str) -> dict[str, Any]:
        """Synchronous clarify (also used after async reaches clarify)."""
        self.last_error = None
        with self._pipeline_lock_obj():
            self.pipeline.answer_clarify(option)
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            return self.snapshot()

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
