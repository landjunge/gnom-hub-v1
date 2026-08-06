"""Application hub: wires EventBus, agents, pipeline, memory, LLM, optional Telegram."""

from __future__ import annotations

import os
from typing import Any

from gnom_hub.agent_ops import AgentOpsMixin
from gnom_hub.agents.manager import AgentManager
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
from gnom_hub.pipeline_api import PipelineApiMixin
from gnom_hub.plugins.loader import PluginLoader
from gnom_hub.plugins.registry import ToolRegistry
from gnom_hub.presets import PresetsMixin
from gnom_hub.security.god_mode import god_mode_from_env
from gnom_hub.session_ops import SessionOpsMixin
from gnom_hub.session_pack import SessionPackMixin
from gnom_hub.snapshot_ops import SnapshotOpsMixin
from gnom_hub.system_ops import SystemOpsMixin
from gnom_hub.telegram.commands import TelegramCommandMixin
from gnom_hub.telegram.lifecycle import TelegramLifecycleMixin
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
    SnapshotOpsMixin,
    PipelineApiMixin,
    TelegramLifecycleMixin,
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
        # Last reasoning stream per agent id (for TTS — not written Box content)
        self._agent_thoughts: dict[str, str] = {}
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
        self._wire_thoughts()
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

    def _wire_thoughts(self) -> None:
        """Capture model reasoning for TTS (Gedanken, not written deliverable)."""

        def on_thought(data: Any) -> None:
            if not isinstance(data, dict):
                return
            aid = str(data.get("id") or "").strip()
            thought = str(data.get("thought") or "").strip()
            if not aid or not thought:
                return
            self._agent_thoughts[aid] = thought[:2500]
            self._append_trace(
                "agent.thought",
                {"id": aid, "chars": len(thought)},
            )

        self.bus.on("agent.thought", on_thought)


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
