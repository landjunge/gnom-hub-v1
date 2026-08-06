"""Tests for AgentManager (v1 step 0.3)."""

from gnom_hub.agents import (
    COLORS,
    DEFAULT_FLEX_PRESET,
    FLEX_PRESETS,
    STATUS_EVENT,
    AgentId,
    AgentManager,
    AgentState,
)
from gnom_hub.core.event_bus import EventBus


def _manager() -> tuple[EventBus, AgentManager, list]:
    bus = EventBus()
    events: list = []
    bus.on(STATUS_EVENT, lambda data: events.append(data))
    mgr = AgentManager(bus)
    return bus, mgr, events


def test_creates_fixed_agents():
    _, mgr, _ = _manager()
    agents = mgr.list_agents()
    ids = [a.id for a in agents]
    assert ids == [
        AgentId.BRAINSTORM,
        AgentId.MEMORY,
        AgentId.FLEX,
        AgentId.COORDINATOR,
        AgentId.WORKER1,
        AgentId.WORKER2,
        AgentId.WORKER3,
        AgentId.WORKER4,
    ]
    assert len(agents) == 8
    assert mgr.get(AgentId.WORKER3).enabled is True
    assert mgr.get(AgentId.WORKER4).enabled is True


def test_colors_and_defaults():
    _, mgr, _ = _manager()
    assert mgr.get(AgentId.BRAINSTORM).color == "red"
    assert mgr.get(AgentId.MEMORY).color == "blue"
    assert mgr.get(AgentId.FLEX).color == "yellow"
    assert mgr.get(AgentId.COORDINATOR).color == "green"
    assert mgr.get(AgentId.WORKER1).color == "orange"
    assert mgr.get(AgentId.WORKER2).color == "purple"
    assert mgr.get(AgentId.WORKER3).color == "teal"
    assert mgr.get(AgentId.WORKER4).color == "gray"

    assert mgr.get(AgentId.MEMORY).enabled is True
    assert mgr.get(AgentId.MEMORY).toggleable is False
    assert mgr.get(AgentId.FLEX).preset == DEFAULT_FLEX_PRESET
    assert DEFAULT_FLEX_PRESET == "personal"
    assert FLEX_PRESETS == ("personal", "security", "neutral", "researcher")
    assert COLORS[AgentId.BRAINSTORM] == "red"


def test_toggle_flip():
    _, mgr, events = _manager()
    assert mgr.get(AgentId.BRAINSTORM).enabled is True
    assert mgr.toggle(AgentId.BRAINSTORM) is False
    assert mgr.get(AgentId.BRAINSTORM).enabled is False
    assert mgr.toggle("brainstorm") is True
    assert mgr.get("brainstorm").enabled is True
    # two status events from toggles
    assert len(events) == 2
    assert events[0]["id"] == "brainstorm"
    assert events[0]["enabled"] is False
    assert events[1]["enabled"] is True


def test_memory_locked():
    _, mgr, events = _manager()
    assert mgr.toggle(AgentId.MEMORY) is True
    assert mgr.get(AgentId.MEMORY).enabled is True
    assert events == []  # no status emit on no-op


def test_enable_all_turns_workers_on():
    _, mgr, _ = _manager()
    mgr.toggle(AgentId.WORKER1)
    mgr.toggle(AgentId.WORKER2)
    mgr.toggle(AgentId.BRAINSTORM)
    assert mgr.get(AgentId.WORKER1).enabled is False
    assert mgr.get(AgentId.WORKER2).enabled is False
    mgr.enable_all()
    assert mgr.get(AgentId.BRAINSTORM).enabled is True
    assert mgr.get(AgentId.WORKER1).enabled is True
    assert mgr.get(AgentId.WORKER2).enabled is True
    # all workers on by default (Box 3 dynamic for 1–4)
    assert mgr.get(AgentId.WORKER3).enabled is True
    assert mgr.get(AgentId.WORKER4).enabled is True


def test_flex_preset():
    _, mgr, events = _manager()
    mgr.set_flex_preset("researcher")
    assert mgr.get(AgentId.FLEX).preset == "researcher"
    assert len(events) == 1
    assert events[0]["id"] == "flex"
    assert events[0]["preset"] == "researcher"
    assert events[0]["role"] == "flex"
    assert events[0]["color"] == "yellow"

    # same preset: no re-emit
    mgr.set_flex_preset("researcher")
    assert len(events) == 1

    mgr.set_flex_preset("Neutral")  # case-insensitive via lower
    assert mgr.get(AgentId.FLEX).preset == "neutral"


def test_flex_preset_unknown():
    _, mgr, _ = _manager()
    try:
        mgr.set_flex_preset("godmode")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "godmode" in str(exc)


def test_on_start_bulk_emit():
    _, mgr, events = _manager()
    mgr.on_start()
    assert len(events) == 8
    ids = {e["id"] for e in events}
    assert ids == {
        "brainstorm",
        "memory",
        "flex",
        "coordinator",
        "worker1",
        "worker2",
        "worker3",
        "worker4",
    }
    flex = next(e for e in events if e["id"] == "flex")
    assert flex["preset"] == "personal"
    memory = next(e for e in events if e["id"] == "memory")
    assert "preset" not in memory


def test_status_payload_fields():
    state = AgentState(
        id=AgentId.FLEX,
        name="Flex",
        role="flex",
        color="yellow",
        enabled=True,
        toggleable=True,
        preset="security",
    )
    payload = state.status_payload()
    assert payload == {
        "id": "flex",
        "enabled": True,
        "role": "flex",
        "color": "yellow",
        "tts": False,
        "preset": "security",
    }


def test_enabled_workers():
    _, mgr, _ = _manager()
    assert len(mgr.enabled_workers()) == 4  # all workers on by default
    mgr.toggle(AgentId.WORKER1)
    workers = mgr.enabled_workers()
    assert len(workers) == 3
    mgr.toggle(AgentId.WORKER3)
    assert len(mgr.enabled_workers()) == 2
    assert AgentId.WORKER2 in [w.id for w in mgr.enabled_workers()]
