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


# Fixed card frame colors (UI later).
COLORS: dict[AgentId, str] = {
    AgentId.BRAINSTORM: "red",
    AgentId.MEMORY: "blue",
    AgentId.FLEX: "yellow",
    AgentId.COORDINATOR: "green",
    AgentId.WORKER1: "orange",
    AgentId.WORKER2: "purple",
}

# Flex role presets (v1). Default is security.
FLEX_PRESETS: tuple[str, ...] = ("security", "neutral", "researcher")
DEFAULT_FLEX_PRESET = "security"


@dataclass
class AgentState:
    id: AgentId
    name: str
    role: str
    color: str
    enabled: bool
    toggleable: bool
    preset: str | None = None

    def status_payload(self) -> dict:
        """Payload for EventBus 'agent.status' events."""
        data: dict = {
            "id": self.id.value,
            "enabled": self.enabled,
            "role": self.role,
            "color": self.color,
        }
        if self.preset is not None:
            data["preset"] = self.preset
        return data
