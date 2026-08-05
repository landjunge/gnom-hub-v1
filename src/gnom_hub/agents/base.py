"""Base agent: enabled gate, EventBus activity, shared LLM call."""

from __future__ import annotations

from typing import Any

from gnom_hub.agents.models import AgentState
from gnom_hub.core.event_bus import EventBus

# Injected into every agent system prompt — kills product-identity hallucination loops
HUB_IDENTITY = (
    "CONTEXT: You are one agent *inside* Gnom-Hub v1, a local multi-agent control hub "
    "(chat → brainstorm → distill → flex → coordinator → workers → memory). "
    "Gnom-Hub is NOT a notes app, NOT a localStorage toy, NOT a single-page notebook. "
    "Never redefine what Gnom-Hub is. "
    "Work ONLY on the user's current task/request. "
    "Do not invent product specs for Gnom-Hub itself unless the user explicitly asks."
)


class BaseAgent:
    def __init__(
        self,
        state: AgentState,
        bus: EventBus,
        llm: Any | None = None,
    ) -> None:
        self.state = state
        self.bus = bus
        self.llm = llm

    @property
    def id(self) -> str:
        return self.state.id.value

    @property
    def enabled(self) -> bool:
        return bool(self.state.enabled)

    def emit_active(self, active: bool = True) -> None:
        payload = self.state.status_payload()
        payload["active"] = active
        self.bus.emit("agent.status", payload)
        self.bus.emit(
            "agent.activity",
            {"id": self.id, "active": active, "enabled": self.enabled},
        )

    def ask(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 500,
        temperature: float = 0.5,
    ) -> str:
        """Call LLM with this agent's model/key override. Raises if no LLM."""
        if self.llm is None:
            raise RuntimeError(f"{self.id}: no LLM manager")
        from gnom_hub.llm.types import LLMMessage

        kwargs: dict[str, Any] = {
            "agent": self.id,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if self.state.model:
            kwargs["model"] = self.state.model
        if self.state.api_key:
            kwargs["api_key"] = self.state.api_key
        sys_full = f"{HUB_IDENTITY}\n\n{system}".strip()
        result = self.llm.chat(
            [
                LLMMessage(role="system", content=sys_full),
                LLMMessage(role="user", content=user),
            ],
            **kwargs,
        )
        return (result.content or "").strip()

    def has_llm(self) -> bool:
        if self.llm is None:
            return False
        has = getattr(self.llm, "has_provider", None)
        if callable(has):
            return bool(has("deepseek")) or bool(self.state.api_key)
        return False
