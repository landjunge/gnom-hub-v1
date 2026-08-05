"""Tests for Pipeline — stub path."""

from gnom_hub.agents import AgentId, AgentManager
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline import DistillQuestion, Pipeline, PipelineStage, PipelineState


def _collect(bus: EventBus) -> list[tuple[str, object]]:
    events: list[tuple[str, object]] = []

    def make(name: str):
        def handler(data):
            events.append((name, data))

        return handler

    for name in (
        "pipeline.stage",
        "pipeline.brainstorm",
        "pipeline.distill",
        "pipeline.question",
        "pipeline.flex",
        "pipeline.coordinate",
        "pipeline.worker",
        "pipeline.done",
        "pipeline.memory_hint",
        "pipeline.error",
    ):
        bus.on(name, make(name))
    return events


def test_reexecute_clears_sticky_error():
    """After a failed execute, a successful re-execute must clear error."""
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn("Build a small dashboard")
    # Simulate prior failure left sticky on state
    pipe.state.error = "simulated LLM outage"
    pipe.state.stage = PipelineStage.error

    state = pipe.execute()
    assert state.stage == PipelineStage.done
    assert state.error is None
    assert state.worker_results
    assert len(state.worker_outputs) >= 1


def test_stub_full_run_no_llm():
    bus = EventBus()
    events = _collect(bus)
    pipe = Pipeline(bus)  # no llm_manager → stubs

    state = pipe.start("Build a landing page")

    assert state.stage == PipelineStage.done
    assert state.error is None
    assert "Build a landing page" in state.brainstorm_notes
    assert "Ideen" in state.brainstorm_notes or "MVP" in state.brainstorm_notes
    assert state.distilled_requirements
    assert state.flex_notes
    assert state.pending_question is None
    assert len(state.worker_results) == 2
    assert "Worker 1" in state.worker_results[0]
    assert "Worker 2" in state.worker_results[1]
    assert len(state.worker_outputs) == 2
    assert state.worker_outputs[0]["worker"] == "worker1"
    assert state.worker_outputs[1]["worker"] == "worker2"
    assert state.worker_outputs[0]["result"] == state.worker_results[0]

    names = [n for n, _ in events]
    assert "pipeline.brainstorm" in names
    assert "pipeline.distill" in names
    assert "pipeline.flex" in names
    assert "pipeline.worker" in names
    assert "pipeline.memory_hint" in names
    assert "pipeline.done" in names
    assert "pipeline.question" not in names
    stages = [d["stage"] for n, d in events if n == "pipeline.stage"]
    # memory recall may emit first, then brainstorm
    assert stages[0] in ("memory", "brainstorm")
    assert "brainstorm" in stages or "flex" in stages
    assert "flex" in stages
    assert stages[-1] == "done"
    assert pipe.state is state


def test_clarify_path_then_continue():
    bus = EventBus()
    events = _collect(bus)
    pipe = Pipeline(bus)

    state = pipe.start("Should we use dark mode maybe?")

    assert state.stage == PipelineStage.clarify
    assert state.pending_question is not None
    assert isinstance(state.pending_question, DistillQuestion)
    assert state.pending_question.options == ["Yes", "No", "Whatever", "Later"]
    assert any(n == "pipeline.question" for n, _ in events)
    assert not any(n == "pipeline.done" for n, _ in events)

    state2 = pipe.answer_clarify("Yes")
    assert state2.stage == PipelineStage.done
    assert state2.pending_question is None
    assert any("clarified" in r.lower() for r in state2.distilled_requirements)
    assert state2.worker_results
    assert state2.flex_notes
    assert any(n == "pipeline.done" for n, _ in events)
    assert any(n == "pipeline.memory_hint" for n, _ in events)
    assert any(n == "pipeline.flex" for n, _ in events)


def test_skip_disabled_brainstorm():
    bus = EventBus()
    events = _collect(bus)
    agents = AgentManager(bus)
    agents.toggle(AgentId.BRAINSTORM)
    assert agents.get(AgentId.BRAINSTORM).enabled is False

    pipe = Pipeline(bus, agent_manager=agents)
    state = pipe.start("Ship feature X")

    assert state.stage == PipelineStage.done
    assert state.brainstorm_notes == ""
    assert not any(n == "pipeline.brainstorm" for n, _ in events)
    assert any(n == "pipeline.distill" for n, _ in events)
    assert any(n == "pipeline.done" for n, _ in events)


def test_skip_disabled_flex():
    bus = EventBus()
    events = _collect(bus)
    agents = AgentManager(bus)
    agents.toggle(AgentId.FLEX)

    pipe = Pipeline(bus, agent_manager=agents)
    state = pipe.start("Ship feature Y")

    assert state.stage == PipelineStage.done
    assert state.flex_notes == ""
    assert not any(n == "pipeline.flex" for n, _ in events)
    assert any(n == "pipeline.done" for n, _ in events)


def test_skip_disabled_coordinator():
    bus = EventBus()
    events = _collect(bus)
    agents = AgentManager(bus)
    agents.toggle(AgentId.COORDINATOR)

    pipe = Pipeline(bus, agent_manager=agents)
    state = pipe.start("Do work")

    assert state.stage == PipelineStage.done
    assert state.worker_results == []
    assert not any(n == "pipeline.worker" for n, _ in events)
    # coordinate event with skipped flag
    coord = [d for n, d in events if n == "pipeline.coordinate"]
    assert coord and coord[0].get("skipped") is True
    assert any(n == "pipeline.memory_hint" for n, _ in events)


def test_skip_disabled_workers():
    bus = EventBus()
    events = _collect(bus)
    agents = AgentManager(bus)
    agents.toggle(AgentId.WORKER1)
    agents.toggle(AgentId.WORKER2)

    pipe = Pipeline(bus, agent_manager=agents)
    state = pipe.start("Do the thing")

    assert state.stage == PipelineStage.done
    assert state.worker_results == []
    assert not any(n == "pipeline.worker" for n, _ in events)
    assert any(n == "pipeline.done" for n, _ in events)
    assert any(n == "pipeline.memory_hint" for n, _ in events)


def test_one_enabled_worker():
    bus = EventBus()
    agents = AgentManager(bus)
    agents.toggle(AgentId.WORKER2)  # only worker1 left

    pipe = Pipeline(bus, agent_manager=agents)
    state = pipe.start("Task A")

    assert state.stage == PipelineStage.done
    assert len(state.worker_results) == 1
    assert "Worker 1" in state.worker_results[0]


def test_flex_preset_security_in_notes():
    bus = EventBus()
    agents = AgentManager(bus)
    agents.set_flex_preset("researcher")
    pipe = Pipeline(bus, agent_manager=agents)
    state = pipe.start("Research topic Z")
    assert state.stage == PipelineStage.done
    assert "Zielgruppe" in state.flex_notes or "Datenquellen" in state.flex_notes


def test_answer_clarify_without_pending_raises():
    pipe = Pipeline(EventBus())
    pipe.start("plain request")
    try:
        pipe.answer_clarify("Yes")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "pending" in str(exc).lower()


def test_pipeline_state_defaults():
    s = PipelineState()
    assert s.stage == PipelineStage.idle
    assert s.worker_results == []
    assert s.distilled_requirements == []
    assert s.flex_notes == ""
    assert s.warnings == []
    q = DistillQuestion(id="x", text="?")
    assert q.options == ["Yes", "No", "Whatever", "Later"]


class _FailLLM:
    def has_provider(self, name: str = "deepseek") -> bool:
        return name == "deepseek"

    def chat(self, *args, **kwargs):
        raise RuntimeError("boom")


def test_llm_failure_falls_back_to_stub():
    bus = EventBus()
    events = _collect(bus)
    bus.on("pipeline.warning", lambda d: events.append(("pipeline.warning", d)))
    pipe = Pipeline(bus, llm_manager=_FailLLM())
    state = pipe.start("Build something solid")
    assert state.stage == PipelineStage.done
    # FailLLM has provider but chat raises → agents fall back to stubs + warnings
    assert state.brainstorm_notes
    assert "Ideen" in state.brainstorm_notes or "MVP" in state.brainstorm_notes
    assert any(n == "pipeline.warning" for n, _ in events)


class _FakeMemory:
    def pipeline_context(self) -> str:
        return "Known facts:\n- Prefer dark theme"


def test_memory_context_injected_into_stub_brainstorm():
    bus = EventBus()
    pipe = Pipeline(bus, memory=_FakeMemory())
    state = pipe.start("Build a landing page")
    assert state.stage == PipelineStage.done
    assert "Prefer dark theme" in state.memory_context
    # stubs always produce useful notes; memory is carried in state for LLM path
    assert state.brainstorm_notes
    assert state.distilled_requirements


def test_garbage_product_identity_facts_filtered():
    """Notes/localStorage toy identity must never re-enter memory or agent context."""
    from gnom_hub.agents.roles import _is_garbage_fact, _sanitize_memory_ctx

    dump_lines = [
        (
            "Gnom-Hub v1 ist ein lokal laufender Notiz-Speicher ohne Backend, "
            "der Notizen als JSON in localStorage ablegt"
        ),
        "XSS-Risiko: bösartiger Notiztext kann Skripte ausführen und localStorage-Daten stehlen",
        "Datenverlust bei Browser-Cache-Leerung – localStorage ist nicht persistent",
        "responsive Liste mit minimalem CSS darstellt",
        "Prefer dark theme for the landing page hero",
        "User wants 3 feature cards and a contact form",
    ]
    assert all(_is_garbage_fact(x) for x in dump_lines[:4])
    assert not _is_garbage_fact(dump_lines[4])
    assert not _is_garbage_fact(dump_lines[5])

    cleaned = _sanitize_memory_ctx("\n".join(dump_lines))
    assert "localStorage" not in cleaned
    assert "Notiz-Speicher" not in cleaned
    assert "responsive Liste" not in cleaned
    assert "Prefer dark theme" in cleaned
    assert "contact form" in cleaned


def test_cooperative_cancel_mid_execute():
    """cancel_check aborts between stages before workers finish."""
    from gnom_hub.pipeline.orchestrator import Pipeline

    class FakeMem:
        def recall(self, t):
            return ""

        def store(self, **kw):
            pass

    bus = EventBus()
    pipe = Pipeline(bus, llm_manager=None, memory=FakeMem())
    pipe.brainstorm_turn("Build a checklist app for cancel test")
    n = {"c": 0}

    def cancel_soon():
        n["c"] += 1
        return n["c"] >= 2

    pipe.cancel_check = cancel_soon
    st = pipe.execute()
    # Should not complete full worker run when cancelled early
    assert n["c"] >= 2
    assert st.stage.value != "done" or not (st.worker_outputs or [])
