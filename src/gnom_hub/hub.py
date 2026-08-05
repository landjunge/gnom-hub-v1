"""Application hub: wires EventBus, agents, pipeline, memory, LLM."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gnom_hub.agents.manager import AgentManager
from gnom_hub.agents.models import FLEX_PRESETS, AgentId, AgentState
from gnom_hub.config.keys import ensure_env_from_key_txt, load_keys
from gnom_hub.config.paths import project_root
from gnom_hub.core.event_bus import EventBus
from gnom_hub.llm.manager import LLMManager
from gnom_hub.memory.atomic import atomic_write_text
from gnom_hub.memory.hot import HotMemory
from gnom_hub.pipeline.pipeline import Pipeline
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
        self.memory = HotMemory(self.root)
        self.pipeline = Pipeline(self.bus, llm_manager=self.llm, agent_manager=self.agents)
        self.last_error: str | None = None
        self._agent_state_path = self.root / "data" / "hot" / "agents.json"
        self._load_agent_state()
        self._wire_memory()
        self.agents.on_start()

    def _wire_memory(self) -> None:
        def on_memory_hint(data: Any) -> None:
            if not isinstance(data, dict):
                return
            user_text = str(data.get("user_text") or "")
            if user_text:
                self.memory.add_message("user", user_text)
            notes = str(data.get("brainstorm_notes") or "")
            if notes:
                self.memory.add_message("brainstorm", notes)
            flex = str(data.get("flex_notes") or "")
            if flex:
                self.memory.add_message("flex", flex)
            for req in data.get("requirements") or []:
                self.memory.add_fact(str(req))
            for res in data.get("results") or []:
                self.memory.add_message("worker", str(res))
            self.memory.save()

        def on_error(data: Any) -> None:
            if isinstance(data, dict):
                self.last_error = str(data.get("error") or "pipeline error")
            else:
                self.last_error = str(data)

        self.bus.on("pipeline.memory_hint", on_memory_hint)
        self.bus.on("pipeline.error", on_error)

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
            # never restore raw api keys from disk for safety in v1

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
        d: dict[str, Any] = {
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
        return d

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
            "brainstorm_notes": st.brainstorm_notes,
            "distilled_requirements": list(st.distilled_requirements),
            "flex_notes": st.flex_notes,
            "pending_question": q,
            "worker_results": list(st.worker_results),
            "warnings": list(st.warnings),
            "error": st.error,
        }

    def snapshot(self) -> dict[str, Any]:
        usage = self.llm.usage_snapshot()
        return {
            "agents": [self._agent_dict(a) for a in self.agents.list_agents()],
            "pipeline": self.pipeline_dict(),
            "memory_summary": self.memory.get_context_summary(),
            "canvas": {
                "mermaid": self.memory.canvas.to_mermaid(),
                "nodes": len(self.memory.canvas.nodes),
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
        self.memory.save()
        agents_path = self._save_agent_state()
        return {
            "ok": True,
            "path": str(self.memory.session_path),
            "agents_path": str(agents_path),
            "summary": self.memory.get_context_summary(),
            "canvas_nodes": len(self.memory.canvas.nodes),
        }

    def reset_session(self, *, keep_agents: bool = True) -> dict[str, Any]:
        """Clear HOT memory/canvas and pipeline state. Agent toggles kept by default."""
        self.memory.clear(save=True)
        self.pipeline = Pipeline(self.bus, llm_manager=self.llm, agent_manager=self.agents)
        self.last_error = None
        if not keep_agents:
            # rebuild defaults
            self.agents = AgentManager(self.bus)
            self.pipeline = Pipeline(self.bus, llm_manager=self.llm, agent_manager=self.agents)
            self.agents.on_start()
        return self.snapshot()

    def help_text(self) -> dict[str, Any]:
        return {
            "title": "Gnom-Hub help",
            "how_to": (
                "1) Type a task in Chat and Send. "
                "2) Double-click cards to toggle agents (Memory always on). "
                "3) Shift+double-click Flex to cycle preset. "
                "4) Answer Box 1 if asked. "
                "5) One Save stores HOT memory + agent state. "
                "6) Reset clears the session."
            ),
            "example": "Chat: 'Plan a small landing page' → see Box 2 ideas and Box 3 results.",
            "pipeline": "Chat → Brainstorm → Distill → [Clarify] → Flex → Coordinator → Workers → Memory",
            "keys": "Put DEEPSEEK_API_KEY in Key.txt (see Key.txt.example). Without key, stubs run.",
        }

    def canvas(self) -> dict[str, Any]:
        return {
            "mermaid": self.memory.canvas.to_mermaid(),
            "nodes": list(self.memory.canvas.nodes),
            "path": str(self.memory.canvas_path),
        }

    def tooltips(self, lang: str = "en") -> dict[str, Any]:
        out: dict[str, Any] = {}
        for tip_id, langs in TOOLTIPS.items():
            block = langs.get(lang) or langs.get("en")
            if block:
                out[tip_id] = dict(block)
        return out


# Process-wide singleton for API
_HUB: Hub | None = None


def get_hub() -> Hub:
    global _HUB
    if _HUB is None:
        _HUB = Hub()
    return _HUB


def reset_hub() -> Hub:
    """Test helper: rebuild hub."""
    global _HUB
    _HUB = Hub()
    return _HUB
