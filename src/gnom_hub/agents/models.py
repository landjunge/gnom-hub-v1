"""Agent identities, colors, and state for v1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgentId(str, Enum):
    BRAINSTORM = "brainstorm"
    MEMORY = "memory"
    FLEX = "flex"
    COORDINATOR = "coordinator"
    WORKER1 = "worker1"
    WORKER2 = "worker2"
    WORKER3 = "worker3"
    WORKER4 = "worker4"


# Fixed card frame colors (plan: 8 agents).
COLORS: dict[AgentId, str] = {
    AgentId.BRAINSTORM: "red",
    AgentId.MEMORY: "blue",
    AgentId.FLEX: "yellow",
    AgentId.COORDINATOR: "green",
    AgentId.WORKER1: "orange",
    AgentId.WORKER2: "purple",
    AgentId.WORKER3: "teal",
    AgentId.WORKER4: "gray",
}

# Flex: personal companion first; optional lenses.
FLEX_PRESETS: tuple[str, ...] = ("personal", "security", "neutral", "researcher")
DEFAULT_FLEX_PRESET = "personal"


@dataclass
class AgentState:
    id: AgentId
    name: str
    role: str
    color: str
    enabled: bool
    toggleable: bool
    preset: str | None = None
    # Optional per-agent LLM override (falls back to global DeepSeek key/model)
    model: str | None = None
    api_key: str | None = None
    # Tuning (plan: agent card click → 5 sliders + prompt)
    system_prompt: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    # UI: read thoughts aloud (browser TTS)
    tts: bool = False

    def status_payload(self) -> dict:
        """Payload for EventBus 'agent.status' events."""
        data: dict = {
            "id": self.id.value,
            "enabled": self.enabled,
            "role": self.role,
            "color": self.color,
            "tts": self.tts,
        }
        if self.preset is not None:
            data["preset"] = self.preset
        if self.model is not None:
            data["model"] = self.model
        return data
