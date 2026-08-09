"""Base agent: enabled gate, EventBus activity, shared LLM call."""

from __future__ import annotations

from typing import Any

from gnom_hub.agents.models import AgentState
from gnom_hub.config.keys import is_usable_api_key
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
        prior: list[dict] | None = None,
    ) -> str:
        """Call LLM with this agent's model/key/tuning overrides. Raises if no LLM.

        prior: optional prior turns [{"role": "user"|"brainstorm"|"assistant", "content"|"text": ...}]
        for multi-turn dialogue (brainstorm chat).
        """
        if self.llm is None:
            raise RuntimeError(f"{self.id}: no LLM manager")
        from gnom_hub.llm.types import LLMMessage

        # Agent tuning wins when set (plan: per-agent sliders)
        temp = (
            float(self.state.temperature)
            if self.state.temperature is not None
            else float(temperature)
        )
        mt = int(self.state.max_tokens) if self.state.max_tokens is not None else int(max_tokens)
        # TTS wants the thinking stream, not the written deliverable.
        # Enable DeepSeek thinking only when this agent has TTS on.
        want_thoughts = bool(getattr(self.state, "tts", False))
        # TTS thinking stream: keep moderate so voice stays short; still need headroom
        if want_thoughts and mt < 900:
            mt = min(1200, max(mt, 900))
        kwargs: dict[str, Any] = {
            "agent": self.id,
            "max_tokens": mt,
            "temperature": temp,
        }
        if want_thoughts:
            kwargs["thinking"] = True
        if self.state.top_p is not None:
            kwargs["top_p"] = float(self.state.top_p)
        if self.state.frequency_penalty is not None:
            kwargs["frequency_penalty"] = float(self.state.frequency_penalty)
        if self.state.presence_penalty is not None:
            kwargs["presence_penalty"] = float(self.state.presence_penalty)
        if self.state.model:
            kwargs["model"] = self.state.model
        if is_usable_api_key(self.state.api_key):
            kwargs["api_key"] = self.state.api_key
        elif str(self.id).startswith("worker") and hasattr(self.llm, "worker_key"):
            wk = self.llm.worker_key()
            if wk:
                kwargs["api_key"] = wk
        # Code role prompt is always the base. Persisted tuning may *append*,
        # never fully replace — old agents.json strings were wiping Brainstorm rules.
        custom = (self.state.system_prompt or "").strip()
        if custom and custom != system.strip():
            role_system = f"{system.strip()}\n\n# Extra agent tuning (user):\n{custom}"
        else:
            role_system = system
        # Spoken Gedanken (reasoning) must be German + short — English TTS was a product bug
        if want_thoughts:
            role_system = (
                f"{role_system.strip()}\n\n"
                "# TTS / thinking stream (mandatory):\n"
                "- Write ALL internal reasoning ONLY in German (Deutsch).\n"
                "- Spoken style, short sentences, max ~50 words of reasoning.\n"
                "- Never English thoughts. Content for the box stays as the role rules say.\n"
            )
        sys_full = f"{HUB_IDENTITY}\n\n{role_system}".strip()
        messages: list[LLMMessage] = [LLMMessage(role="system", content=sys_full)]
        for item in (prior or [])[-16:]:
            if not isinstance(item, dict):
                continue
            raw_role = str(item.get("role") or "user").strip().lower()
            content = str(item.get("content") or item.get("text") or "").strip()
            if not content:
                continue
            if raw_role in ("brainstorm", "assistant", "agent"):
                messages.append(LLMMessage(role="assistant", content=content[:2000]))
            elif raw_role == "system":
                continue
            else:
                messages.append(LLMMessage(role="user", content=content[:2000]))
        messages.append(LLMMessage(role="user", content=user))
        result = self.llm.chat(messages, **kwargs)
        thought = (getattr(result, "reasoning", None) or "").strip()
        if thought:
            self.bus.emit(
                "agent.thought",
                {
                    "id": self.id,
                    "thought": thought[:2500],
                    "label": self.state.name or self.id,
                },
            )
        return (result.content or "").strip()

    def has_llm(self) -> bool:
        if self.llm is None:
            return False
        has = getattr(self.llm, "has_provider", None)
        if callable(has):
            return (
                bool(has("deepseek"))
                or bool(has("ollama"))
                or bool(has("any"))
                or is_usable_api_key(self.state.api_key)
            )
        return False
