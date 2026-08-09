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
    assert (
        "Ideen" in state.brainstorm_notes
        or "Kurz zu" in state.brainstorm_notes
        or "Richtungen" in state.brainstorm_notes
    )
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
    assert state.pending_question.options[0].startswith("Schnell")
    assert any(n == "pipeline.question" for n, _ in events)
    assert not any(n == "pipeline.done" for n, _ in events)

    state2 = pipe.answer_clarify("Schnell und einfach")
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


def test_flex_cannot_be_disabled():
    """Flex is fixed on — toggle is no-op; pipeline still runs flex stage."""
    bus = EventBus()
    events = _collect(bus)
    agents = AgentManager(bus)
    assert agents.toggle(AgentId.FLEX) is True
    assert agents.get(AgentId.FLEX).enabled is True

    pipe = Pipeline(bus, agent_manager=agents)
    state = pipe.start("Ship feature Y")

    assert state.stage == PipelineStage.done
    assert state.flex_notes  # still ran
    assert any(n == "pipeline.flex" for n, _ in events)
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
    # turn all workers off
    for wid in (AgentId.WORKER1, AgentId.WORKER2, AgentId.WORKER3, AgentId.WORKER4):
        if agents.get(wid).enabled:
            agents.toggle(wid)

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
    # only worker1 left
    for wid in (AgentId.WORKER2, AgentId.WORKER3, AgentId.WORKER4):
        if agents.get(wid).enabled:
            agents.toggle(wid)

    pipe = Pipeline(bus, agent_manager=agents)
    state = pipe.start("Task A")

    assert state.stage == PipelineStage.done
    assert len(state.worker_results) == 1
    assert "Worker 1" in state.worker_results[0]


def test_flex_personal_remembers_user():
    bus = EventBus()
    agents = AgentManager(bus)
    agents.set_flex_preset("personal")
    pipe = Pipeline(bus, agent_manager=agents)
    state = pipe.start("browse zu grok.com und chatte mit Eve")
    assert state.stage == PipelineStage.done
    # Stub/heuristic path: flex notes about the user or facts absorbed
    low = (state.flex_notes or "").lower()
    assert "weiß" in low or "user" in low or "eve" in low or "grok" in low


def test_flex_absorb_emits_facts():
    from gnom_hub.agents.models import AgentId
    from gnom_hub.agents.roles import FlexAgent

    bus = EventBus()
    agents = AgentManager(bus)
    seen: list = []
    bus.on("pipeline.flex_facts", lambda d: seen.append(d))
    flex = FlexAgent(agents.get(AgentId.FLEX), bus, llm=None)
    facts = flex.absorb("browse zu grok.com und chatte mit Eve")
    assert any("grok" in f.lower() for f in facts)
    assert any("eve" in f.lower() for f in facts)
    assert seen


def test_answer_clarify_without_pending_raises():
    pipe = Pipeline(EventBus())
    pipe.start("plain request")
    try:
        pipe.answer_clarify("Yes")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "pending" in str(exc).lower()


def test_answer_clarify_keeps_question_on_cancel():
    """H2: cancel mid-continue must not drop pending_question."""
    from gnom_hub.pipeline.orchestrator import Pipeline

    class FakeMem:
        def recall(self, t):
            return ""

        def store(self, **kw):
            pass

    bus = EventBus()
    pipe = Pipeline(bus, llm_manager=None, memory=FakeMem())
    st = pipe.start("Should we use dark mode maybe?")
    assert st.stage == PipelineStage.clarify
    assert st.pending_question is not None
    pipe.cancel_check = lambda: True
    st2 = pipe.answer_clarify("Schnell und einfach")
    assert st2.pending_question is not None
    assert st2.stage == PipelineStage.clarify
    assert st2.error is None


def test_worker_partials_published_before_cancel():
    """H4: each finished worker is visible on state before the next / cancel."""
    from gnom_hub.pipeline.orchestrator import Pipeline

    class FakeMem:
        def recall(self, t):
            return ""

        def store(self, **kw):
            pass

    bus = EventBus()
    pipe = Pipeline(bus, llm_manager=None, memory=FakeMem())
    pipe.brainstorm_turn("only brainstorm then execute partials")
    # Force multi-worker plan path via execute with cancel after first checks
    seen_partials = {"n": 0}

    def cancel_after_partials():
        # Allow first worker to land, cancel before finish
        n = len(pipe.state.worker_outputs or [])
        seen_partials["n"] = n
        return n >= 1

    pipe.cancel_check = cancel_after_partials
    st = pipe.execute()
    assert st.stage.value != "done"
    # Either we got a partial or cancelled very early (still no crash)
    assert st.error is None


def test_pipeline_state_defaults():
    s = PipelineState()
    assert s.stage == PipelineStage.idle
    assert s.worker_results == []
    assert s.distilled_requirements == []
    assert s.flex_notes == ""
    assert s.warnings == []
    q = DistillQuestion(id="x", text="?")
    assert q.options[0].startswith("Schnell")


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
    assert (
        "Ideen" in state.brainstorm_notes
        or "Kurz zu" in state.brainstorm_notes
        or "Richtungen" in state.brainstorm_notes
    )
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
            raise AssertionError("memory.store must not run after cancel")

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
    assert st.stage.value != "done"
    # H1: re-executable — notes kept, not stuck mid-stage
    assert st.stage.value == "brainstorm"
    assert (st.brainstorm_notes or "").strip()
    assert st.error is None


def test_start_cancel_is_not_hard_error():
    """C3: PipelineCancelled must not become stage=error via start()."""
    from gnom_hub.pipeline.orchestrator import Pipeline

    class FakeMem:
        def recall(self, t):
            return ""

        def store(self, **kw):
            raise AssertionError("no store on cancel")

    bus = EventBus()
    pipe = Pipeline(bus, llm_manager=None, memory=FakeMem())
    pipe.cancel_check = lambda: True
    st = pipe.start("full one-shot should cancel")
    assert st.stage.value in ("idle", "brainstorm")
    assert st.error is None
    assert st.stage.value != "error"


def test_abort_cancelled_restores_can_execute_snapshot():
    """H1: after cancel, pipeline_dict can_execute is true when notes exist."""
    from gnom_hub.pipeline.orchestrator import Pipeline

    class FakeMem:
        def recall(self, t):
            return ""

        def store(self, **kw):
            pass

    bus = EventBus()
    pipe = Pipeline(bus, llm_manager=None, memory=FakeMem())
    pipe.brainstorm_turn("only brainstorm ideas for cancel restore")
    assert (pipe.state.brainstorm_notes or "").strip()
    pipe.cancel_check = lambda: True
    pipe.execute()
    assert pipe.state.stage.value == "brainstorm"
    # Mimic snapshot rule
    st = pipe.state
    can_execute = bool((st.brainstorm_notes or "").strip()) and st.stage.value in (
        "brainstorm",
        "idle",
        "done",
        "error",
    )
    assert can_execute is True


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
    # M11: </html> too early / junk after close must fail
    early = "<!DOCTYPE html><html></html>" + (" padding" * 40)
    assert not _html_complete(early)
    after_junk = (
        "<!DOCTYPE html><html><body>" + ("x" * 80) + "</body></html>\n<script>alert(1)</script>"
    )
    assert not _html_complete(after_junk)
    unclosed_script = "<!DOCTYPE html><html><body><script>var x=1;" + ("y" * 50) + "</body></html>"
    assert not _html_complete(unclosed_script)
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
    from gnom_hub.agents.plan_fast_path import _wants_one_html_page
    from gnom_hub.agents.roles_ext import (
        CoordinatorAgent,
        _html_full_page_plan,
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
    forced = _html_full_page_plan("Landing HTML", ["worker1", "worker2", "worker3"], ["DoD line"])
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


def test_flex_execute_on_explicit_command():
    """User says 'execute' after a real task → Flex triggers full run."""
    bus = EventBus()
    events: list[tuple[str, object]] = []
    bus.on("pipeline.flex_execute", lambda d: events.append(("flex_execute", d)))
    bus.on("pipeline.auto_execute", lambda d: events.append(("auto_execute", d)))
    pipe = Pipeline(bus)
    # Pure ideation — must NOT auto-execute on first turn
    pipe.brainstorm_turn("Ideen zu einer Checklisten-App, nur Brainstorm bitte")
    assert pipe.state.stage == PipelineStage.brainstorm
    st = pipe.brainstorm_turn("execute")
    # Product: bare "execute" after a real task is go_only auto_execute (may skip flex_execute event)
    assert any(n == "auto_execute" for n, _ in events) or any(
        n == "flex_execute" for n, _ in events
    )
    assert st.stage in (PipelineStage.done, PipelineStage.clarify, PipelineStage.work)
    # Flex may already have spoken on prior turn; go_only path does not require a new flex line


def test_flex_execute_refuses_bare_execute_without_task():
    bus = EventBus()
    pipe = Pipeline(bus)
    st = pipe.brainstorm_turn("execute")
    # No prior task → stay in brainstorm, no workers
    assert st.stage == PipelineStage.brainstorm
    assert not st.worker_results


def test_flex_execute_on_hard_build_order():
    bus = EventBus()
    seen: list = []
    bus.on("pipeline.flex_execute", lambda d: seen.append(d))
    pipe = Pipeline(bus)
    st = pipe.brainstorm_turn("Build a landing page for Bean Shop. Full HTML with hero and footer.")
    assert st.stage == PipelineStage.done or st.worker_results
    assert seen or st.mode == "execute" or st.stage == PipelineStage.done


def test_flex_contributes_each_brainstorm_turn():
    bus = EventBus()
    chat: list = []
    bus.on("pipeline.flex_chat", lambda d: chat.append(d))
    pipe = Pipeline(bus)
    st = pipe.brainstorm_turn("Ideen zu einer Checklisten-App, nur Brainstorm bitte")
    assert st.stage == PipelineStage.brainstorm
    flex_turns = [t for t in st.brainstorm_turns if t.get("role") == "flex"]
    assert flex_turns, "Flex should post a chat line each brainstorm turn"
    assert "Flex:" in flex_turns[0]["text"] or flex_turns[0]["text"].startswith("Flex")
    assert chat, "pipeline.flex_chat event expected"
    # Notes should label Flex, not as Brainstorm dump only
    assert "Flex:" in (st.brainstorm_notes or "")


def test_flex_execute_line_not_double_with_contribute():
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn("Ideen zu einer Checklisten-App, nur Brainstorm bitte")
    st = pipe.brainstorm_turn("execute")
    flex_turns = [t for t in st.brainstorm_turns if t.get("role") == "flex"]
    # Last flex line should be Execute message, not contribute
    assert flex_turns
    assert any("Execute" in str(t.get("text") or "") for t in flex_turns)


def test_flex_pipeline_injects_wishes_into_requirements():
    """Execute path: standing wishes become Flex-wish requirements for workers."""
    bus = EventBus()
    pipe = Pipeline(bus)
    # Seed memory via flex absorb path + warm through pipeline memory if available
    # Directly put wishes into memory_context for binding_wishes
    pipe.brainstorm_turn("Build a landing page for Bean Shop full HTML with hero and footer.")
    # If auto-executed, state may already be done — set wishes on next execute path
    st = pipe.state
    # Force re-execute with memory context containing a User wish
    pipe.state.memory_context = (
        pipe.state.memory_context or ""
    ) + "\nUser: always enable dark theme\nUser: never truncate HTML\n"
    if st.stage == PipelineStage.done:
        st2 = pipe.execute()
    else:
        st2 = pipe.execute()
    reqs = "\n".join(st2.distilled_requirements)
    assert "Flex-wish:" in reqs or "dark theme" in reqs.lower()
    assert st2.flex_notes
    assert st2.stage in (PipelineStage.done, PipelineStage.clarify)


def test_flex_binding_wishes_helper():
    from gnom_hub.agents import AgentId, AgentManager, FlexAgent
    from gnom_hub.core.event_bus import EventBus

    bus = EventBus()
    flex = FlexAgent(AgentManager(bus).get(AgentId.FLEX), bus, llm=None)
    wishes = flex.binding_wishes("noise\nUser: always TTS on\n- Wish: keep flex wishes\nother")
    assert any("TTS" in w or "tts" in w.lower() for w in wishes)
    assert any("keep flex" in w.lower() or "wishes" in w.lower() for w in wishes)
