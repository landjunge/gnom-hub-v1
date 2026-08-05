"""Application hub: wires EventBus, agents, pipeline, memory, LLM."""

from __future__ import annotations

from typing import Any

from gnom_hub.agents.manager import AgentManager
from gnom_hub.agents.models import FLEX_PRESETS, AgentId, AgentState
from gnom_hub.config.keys import ensure_env_from_key_txt, load_keys
from gnom_hub.config.paths import project_root
from gnom_hub.core.event_bus import EventBus
from gnom_hub.llm.manager import LLMManager
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

        self.bus.on("pipeline.memory_hint", on_memory_hint)

    # ── serialization ───────────────────────────────────────────────

    @staticmethod
    def _agent_dict(a: AgentState) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": a.id.value,
            "name": a.name,
            "role": a.role,
            "color": a.color,
            "enabled": a.enabled,
            "toggleable": a.toggleable,
            "preset": a.preset,
            "model": a.model,
            "has_key": bool(a.api_key),
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
            "error": st.error,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "agents": [self._agent_dict(a) for a in self.agents.list_agents()],
            "pipeline": self.pipeline_dict(),
            "memory_summary": self.memory.get_context_summary(),
            "llm": {
                "deepseek": self.llm.has_provider("deepseek"),
                "free_only": self.llm.free_only,
                "max_budget_usd": self.llm.max_budget_usd,
                "spent_usd": self.llm.spent_usd,
                "default_model": self.llm.default_model,
            },
            "flex_presets": list(FLEX_PRESETS),
        }

    # ── commands ────────────────────────────────────────────────────

    def chat(self, text: str) -> dict[str, Any]:
        self.pipeline.start(text)
        return self.snapshot()

    def clarify(self, option: str) -> dict[str, Any]:
        self.pipeline.answer_clarify(option)
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
        return {
            "ok": True,
            "path": str(self.memory.session_path),
            "summary": self.memory.get_context_summary(),
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
