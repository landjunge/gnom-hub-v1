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
from gnom_hub.pipeline.pipeline import Pipeline
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
        self.memory = MemoryFacade(self.hot, self.warm)
        self.workspace = WorkspaceStore(self.root)
        self.cold = ColdArchive(self.root)
        self.vectors = VectorStore(self.root)
        self.god_mode = god_mode_from_env()
        self.computer = ComputerUseKit(self.root, god_mode=self.god_mode.enabled)
        self.tools = ToolRegistry()
        self.plugins = PluginLoader(self.root / "plugins", self.tools)
        self._register_core_tools()
        self.plugin_list = self.plugins.discover_and_load()
        self.pipeline = self._new_pipeline()
        self.last_error: str | None = None
        self._agent_state_path = self.root / "data" / "hot" / "agents.json"
        self.telegram = self._init_telegram()
        self._load_agent_state()
        self._wire_memory()
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
                description="Run chat pipeline with a task",
                handler=lambda text: {
                    "stage": self.chat(str(text))["pipeline"]["stage"],
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
            for req in data.get("requirements") or []:
                text = str(req)
                self.hot.add_fact(text)
                # Promote short requirements to WARM (durable)
                if 8 <= len(text) <= 240:
                    self.warm.add_fact(text)
                self.vectors.add(text, meta={"source": "requirement"})
            for res in data.get("results") or []:
                self.hot.add_message("worker", str(res))
                self.vectors.add(str(res)[:500], meta={"source": "worker"})
            self.hot.save()

        def on_error(data: Any) -> None:
            if isinstance(data, dict):
                self.last_error = str(data.get("error") or "pipeline error")
            else:
                self.last_error = str(data)

        self.bus.on("pipeline.memory_hint", on_memory_hint)
        self.bus.on("pipeline.error", on_error)

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
            snap = self.chat(arg.strip())
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

    def _save_agent_state(self) -> Path:
        payload = {
            "agents": [
                {
                    "id": a.id.value,
                    "enabled": a.enabled,
                    "preset": a.preset,
                    "model": a.model,
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
        return {
            "id": a.id.value,
            "name": a.name,
            "role": a.role,
            "color": a.color,
            "enabled": a.enabled,
            "toggleable": a.toggleable,
            "preset": a.preset,
            "model": a.model or self.llm.default_model,
            "has_key": bool(a.api_key) or self.llm.has_provider("deepseek"),
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
        return {
            "stage": st.stage.value,
            "user_text": st.user_text,
            "memory_context": st.memory_context,
            "brainstorm_notes": st.brainstorm_notes,
            "distilled_requirements": list(st.distilled_requirements),
            "flex_notes": st.flex_notes,
            "pending_question": q,
            "worker_results": list(st.worker_results),
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
                "free_only": self.llm.free_only,
                "max_budget_usd": self.llm.max_budget_usd,
                "spent_usd": usage["spent_usd"],
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "default_model": self.llm.default_model,
            },
            "flex_presets": list(FLEX_PRESETS),
            "last_error": self.last_error,
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

    def chat(self, text: str) -> dict[str, Any]:
        self.last_error = None
        self.pipeline.start(text)
        if self.pipeline.state.error:
            self.last_error = self.pipeline.state.error
        return self.snapshot()

    def clarify(self, option: str) -> dict[str, Any]:
        self.last_error = None
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
        return self._agent_dict(agent)

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
        self, *, keep_agents: bool = True, clear_warm: bool = False
    ) -> dict[str, Any]:
        """Clear HOT session. WARM kept unless clear_warm=True."""
        self.hot.clear(save=True)
        if clear_warm:
            self.warm.clear()
        if not keep_agents:
            self.agents = AgentManager(self.bus)
            self.agents.on_start()
        self.pipeline = self._new_pipeline()
        self.last_error = None
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

    def help_text(self) -> dict[str, Any]:
        return {
            "title": "Gnom-Hub help",
            "how_to": (
                "1) Type a task in Chat and Send. "
                "2) Double-click cards to toggle agents (Memory always on). "
                "3) Shift+double-click Flex to cycle preset. "
                "4) Answer Box 1 if asked. "
                "5) Save stores HOT + WARM + agent state. "
                "6) Reset clears HOT only (WARM facts stay). "
                "7) Optional Telegram: TELEGRAM_BOT_TOKEN + GNOM_TELEGRAM_POLL=1."
            ),
            "example": "Chat: 'Plan a small landing page' → Box 2 ideas, Box 3 results.",
            "pipeline": "Chat → Brainstorm → Distill → [Clarify] → Flex → Coordinator → Workers → Memory",
            "keys": "DEEPSEEK_API_KEY in Key.txt. Optional TELEGRAM_BOT_TOKEN.",
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
