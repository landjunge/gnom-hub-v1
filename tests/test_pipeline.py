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
    # Landing/HTML → exactly one worker builds the page
    assert len(state.worker_results) == 1
    assert "Worker 1" in state.worker_results[0]
    assert len(state.worker_outputs) == 1
    assert state.worker_outputs[0]["worker"] == "worker1"
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


def test_html_gates_and_dod():
    from gnom_hub.pipeline.orchestrator import (
        _definition_of_done,
        _html_complete,
        _quality_check,
        _validate_worker_draft,
    )

    assert "DEFINITION OF DONE" in _definition_of_done("landing", ["complete HTML"])
    assert _html_complete("<!DOCTYPE html><html><body>x</body></html>")
    assert not _html_complete("<html><body>open")
    bad = _validate_worker_draft("<html>partial", user_text="landing html page", task="html")
    assert bad["ok"] is False
    notes = _quality_check(
        "landing html",
        ["full doc"],
        [
            {
                "name": "W1",
                "result": "<!DOCTYPE html><html><body>ok</body></html>",
                "task": "html",
                "validation": {"ok": True, "issues": []},
            }
        ],
    )
    assert "Gates:" in notes


def test_brainstorm_topic_switch_resets_dialogue():
    """Unrelated long new task must not keep prior turns (e.g. TTS → landing page)."""
    from gnom_hub.pipeline.orchestrator import _is_topic_switch

    turns = [{"role": "user", "text": "was ist mit tts"}, {"role": "brainstorm", "text": "…"}]
    landing = (
        "Build a modern landing page for a coffee shop called Bean & Bloom. "
        "Include hero with headline and CTA, three feature cards, and a simple footer. "
        "Output full HTML with inline CSS."
    )
    assert _is_topic_switch(turns, landing) is True
    assert _is_topic_switch(turns, "ok more detail please") is False

    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn("was ist mit tts")
    assert "tts" in (pipe.state.user_text or "").lower()
    pipe.brainstorm_turn(landing)
    assert "landing" in (pipe.state.user_text or "").lower()
    assert "tts" not in (pipe.state.user_text or "").lower()
    # Fresh dialogue — first user turn is the landing task
    user_turns = [t for t in pipe.state.brainstorm_turns if t.get("role") == "user"]
    assert len(user_turns) == 1
    assert "Bean" in user_turns[0]["text"]


def test_execute_uses_latest_user_turn():
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn("First idea about a todo list MVP")
    pipe.brainstorm_turn("Also consider dark mode for the same todo list")
    # Same topic → multi-turn; user_text is latest
    assert "dark mode" in (pipe.state.user_text or "").lower()
    st = pipe.execute()
    assert st.stage == PipelineStage.done
    assert "dark mode" in (st.user_text or "").lower()


def test_coordinator_html_plan_prefers_full_page():
    """HTML/landing tasks always get deterministic full-page plan (no section splits)."""
    from gnom_hub.agents.models import COLORS, AgentId, AgentState
    from gnom_hub.agents.roles_ext import (
        CoordinatorAgent,
        _html_full_page_plan,
        _wants_one_html_page,
    )
    from gnom_hub.core.event_bus import EventBus

    st = AgentState(
        id=AgentId.COORDINATOR,
        name="Coordinator",
        role="coordinator",
        color=COLORS[AgentId.COORDINATOR],
        enabled=True,
        toggleable=True,
    )
    coord = CoordinatorAgent(st, EventBus(), llm=None)
    tasks = coord.plan(
        "Build a landing page with hero, features, footer. Full HTML.",
        ["complete HTML"],
        ["worker1", "worker2", "worker3"],
    )
    assert len(tasks) == 1
    assert tasks[0][0] == "worker1"
    assert "ONE complete single-file HTML" in tasks[0][1]
    assert "ALL requested sections" in tasks[0][1]
    assert "hero section only" not in tasks[0][1].lower()
    assert _wants_one_html_page("landing page HTML")
    assert not _wants_one_html_page("write a business plan")
    forced = _html_full_page_plan(
        "Landing HTML", ["worker1", "worker2", "worker3"], ["DoD line"]
    )
    assert len(forced) == 1
    assert forced[0][0] == "worker1"
    assert "DoD:" in forced[0][1]
    qa = coord.plan(
        "Review the checkout flow", ["tests"], ["worker1", "worker2"], plan_mode="plan_qa"
    )
    assert "QA checklist" in qa[0][1]
    html_forced = coord.plan(
        "something without keywords",
        [],
        ["worker1"],
        plan_mode="full_page_html",
    )
    assert "ONE complete single-file HTML" in html_forced[0][1]
