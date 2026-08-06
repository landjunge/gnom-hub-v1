"""AgentManager: fixed v1 agents, toggle, flex presets, status events."""

from __future__ import annotations

from gnom_hub.agents.models import (
    COLORS,
    DEFAULT_FLEX_PRESET,
    FLEX_PRESETS,
    AgentId,
    AgentState,
)
from gnom_hub.core.event_bus import EventBus

STATUS_EVENT = "agent.status"

# Plan: up to 4 workers (3/4 off by default so pipelines stay light)
_WORKER_IDS: tuple[AgentId, ...] = (
    AgentId.WORKER1,
    AgentId.WORKER2,
    AgentId.WORKER3,
    AgentId.WORKER4,
)


class AgentManager:
    """Owns the fixed agent set and emits live status on the EventBus."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._agents: dict[AgentId, AgentState] = self._build_agents()

    def _build_agents(self) -> dict[AgentId, AgentState]:
        specs: list[tuple[AgentId, str, str, bool, bool, str | None]] = [
            # id, name, role, enabled, toggleable, preset
            (AgentId.BRAINSTORM, "Brainstorm", "brainstorm", True, True, None),
            (AgentId.MEMORY, "Memory", "memory", True, False, None),
            (AgentId.FLEX, "Flex", "flex", True, True, DEFAULT_FLEX_PRESET),
            (AgentId.COORDINATOR, "Coordinator", "coordinator", True, True, None),
            # All workers on by default (user: Box 3 dynamic for 1+2+…; enable off workers)
            (AgentId.WORKER1, "Worker 1", "worker", True, True, None),
            (AgentId.WORKER2, "Worker 2", "worker", True, True, None),
            (AgentId.WORKER3, "Worker 3", "worker", True, True, None),
            (AgentId.WORKER4, "Worker 4", "worker", True, True, None),
        ]
        agents: dict[AgentId, AgentState] = {}
        for agent_id, name, role, enabled, toggleable, preset in specs:
            agents[agent_id] = AgentState(
                id=agent_id,
                name=name,
                role=role,
                color=COLORS[agent_id],
                enabled=enabled,
                toggleable=toggleable,
                preset=preset,
            )
        return agents

    def on_start(self) -> None:
        """Bulk-emit current status for all agents (UI bootstrap)."""
        for agent in self._agents.values():
            self._emit_status(agent)

    def get(self, agent_id: AgentId | str) -> AgentState:
        return self._agents[self._resolve_id(agent_id)]

    def list_agents(self) -> list[AgentState]:
        """Agents in stable card order (8 slots)."""
        order = [
            AgentId.BRAINSTORM,
            AgentId.MEMORY,
            AgentId.FLEX,
            AgentId.COORDINATOR,
            AgentId.WORKER1,
            AgentId.WORKER2,
            AgentId.WORKER3,
            AgentId.WORKER4,
        ]
        return [self._agents[aid] for aid in order]

    def toggle(self, agent_id: AgentId | str) -> bool:
        """
        Flip enabled for toggleable agents.

        Memory is locked on: no-op, returns True (still enabled).
        """
        aid = self._resolve_id(agent_id)
        agent = self._agents[aid]
        if not agent.toggleable:
            # Memory (and any future locked agents): stay enabled.
            return agent.enabled

        agent.enabled = not agent.enabled
        self._emit_status(agent)
        return agent.enabled

    def set_flex_preset(self, name: str) -> None:
        """Set Flex preset. Raises ValueError if unknown."""
        key = name.strip().lower()
        if key not in FLEX_PRESETS:
            raise ValueError(f"Unknown flex preset: {name!r}. Allowed: {FLEX_PRESETS}")
        flex = self._agents[AgentId.FLEX]
        if flex.preset == key:
            return
        flex.preset = key
        self._emit_status(flex)

    def enabled_workers(self) -> list[AgentState]:
        """Enabled workers only (up to 4)."""
        return [self._agents[aid] for aid in _WORKER_IDS if self._agents[aid].enabled]

    def enable_all(self, *, include_extra_workers: bool = True) -> list[AgentState]:
        """Turn all agents on (Worker3/4 included by default)."""
        for agent in self._agents.values():
            if agent.id in (AgentId.WORKER3, AgentId.WORKER4) and not include_extra_workers:
                continue
            if not agent.enabled:
                agent.enabled = True
                self._emit_status(agent)
        return self.list_agents()

    def emit_status(self, agent_id: AgentId | str) -> None:
        """Re-broadcast one agent's status (e.g. after LLM override change)."""
        self._emit_status(self._agents[self._resolve_id(agent_id)])

    def _emit_status(self, agent: AgentState) -> None:
        self._bus.emit(STATUS_EVENT, agent.status_payload())

    @staticmethod
    def _resolve_id(agent_id: AgentId | str) -> AgentId:
        if isinstance(agent_id, AgentId):
            return agent_id
        return AgentId(agent_id)
