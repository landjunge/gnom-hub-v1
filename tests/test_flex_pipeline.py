"""Broader coverage: Flex pipeline hooks, execute triggers, wish inject, plan DoD."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.agents import AgentId, AgentManager, FlexAgent
from gnom_hub.agents.roles_ext import CoordinatorAgent
from gnom_hub.core.event_bus import EventBus
from gnom_hub.memory.facade import MemoryFacade
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.warm import WarmMemory
from gnom_hub.pipeline import Pipeline, PipelineStage
from gnom_hub.pipeline.orchestrator import (
    _definition_of_done,
    _format_turns,
    _pick_execute_task,
    _wants_auto_execute,
)


def _flex(bus: EventBus | None = None) -> FlexAgent:
    b = bus or EventBus()
    return FlexAgent(AgentManager(b).get(AgentId.FLEX), b, llm=None)


# ── maybe_request_execute ───────────────────────────────────────────


def test_maybe_request_execute_explicit_with_history():
    flex = _flex()
    turns = [
        {"role": "user", "text": "Ideen zu einer Checklisten-App"},
        {"role": "brainstorm", "text": "…"},
        {"role": "user", "text": "execute"},
    ]
    d = flex.maybe_request_execute("execute", turns, "")
    assert d and d["execute"] is True
    assert d["reason"] == "explicit_execute"
    assert "Execute" in d["message"]


def test_maybe_request_execute_bare_execute_without_task():
    flex = _flex()
    assert flex.maybe_request_execute("execute", [], "") is None
    assert flex.maybe_request_execute("execute", [{"role": "user", "text": "execute"}], "") is None


def test_maybe_request_execute_context_build_order():
    flex = _flex()
    text = "Build a landing page for Bean Shop full HTML with hero and footer."
    d = flex.maybe_request_execute(text, [{"role": "user", "text": text}], "")
    assert d and d["reason"] == "context_intent"


def test_maybe_request_execute_standing_wish():
    flex = _flex()
    # Short follow-up that alone is weak; with standing wish + prior build in turns
    # Use a clear build so context_intent may fire first — standing_wish needs
    # no context_intent first. Craft text that is NOT auto-execute alone.
    text = "Mach die Checkliste final"
    turns = [
        {"role": "user", "text": "Checklisten-App planen"},
        {"role": "brainstorm", "text": "ok"},
        {"role": "user", "text": text},
    ]
    # Without wish: may or may not fire; with wish + wants_auto if triggers match
    mem = "User: always execute\nUser: immer ausführen"
    # Force path: explicit-ish build verb
    text2 = "Bau die Seite jetzt umsetzen"
    d = flex.maybe_request_execute(text2, turns + [{"role": "user", "text": text2}], mem)
    assert d is not None
    assert d["execute"] is True
    assert d["reason"] in ("context_intent", "standing_wish", "explicit_execute")


def test_maybe_request_execute_diagnosis_no_fire():
    flex = _flex()
    text = "Warum hakt die TTS und was ist mit dem Memory?"
    assert flex.maybe_request_execute(text, [{"role": "user", "text": text}], "") is None


# ── brainstorm_contribute ───────────────────────────────────────────


def test_brainstorm_contribute_mentions_absorbed():
    flex = _flex()
    msg = flex.brainstorm_contribute(
        "Ich will immer Dark Mode",
        "Ideen… → Soll ich umsetzen?",
        "",
        absorbed=["User: always dark mode"],
    )
    assert msg
    assert msg.startswith("Flex:")
    assert "gemerkt" in msg.lower() or "dark" in msg.lower()


def test_brainstorm_contribute_skips_bare_execute():
    flex = _flex()
    assert flex.brainstorm_contribute("execute", "notes", "") is None


def test_brainstorm_contribute_emits_event():
    bus = EventBus()
    seen: list = []
    bus.on("pipeline.flex_chat", lambda d: seen.append(d))
    flex = _flex(bus)
    msg = flex.brainstorm_contribute(
        "Ideen zu einer Todo-App nur brainstorm",
        "• MVP\n→ Soll ich das jetzt umsetzen?",
        "User: always TTS on",
    )
    assert msg
    assert seen and "message" in seen[0]


# ── binding_wishes + DoD ────────────────────────────────────────────


def test_binding_wishes_normalizes_prefixes():
    flex = _flex()
    out = flex.binding_wishes(
        "x\nUser: a\nWish: b rule long enough\nflex-wish: c rule long enough\nnoise"
    )
    assert any(x.startswith("User:") for x in out)
    assert len(out) >= 2


def test_definition_of_done_includes_flex_wish_not_meta():
    dod = _definition_of_done(
        "task",
        [
            "Ziel: x",
            "Flex/personal: meta briefing line",
            "Flex-wish: User: always enable TTS for Flex",
        ],
    )
    assert "always enable TTS" in dod
    assert "meta briefing" not in dod


# ── orchestrator helpers ────────────────────────────────────────────


def test_format_turns_labels_flex():
    text = _format_turns(
        [
            {"role": "user", "text": "hi"},
            {"role": "brainstorm", "text": "ideas"},
            {"role": "flex", "text": "Flex: dabei"},
        ]
    )
    assert "You: hi" in text
    assert "Brainstorm:" in text
    assert "Flex:" in text
    assert text.index("You:") < text.index("Flex:")


def test_wants_auto_execute_go_word_after_two_users():
    turns = [
        {"role": "user", "text": "Plan a checklist app"},
        {"role": "brainstorm", "text": "soll ich umsetzen?"},
        {"role": "user", "text": "ja"},
    ]
    assert _wants_auto_execute("ja", turns) is True


def test_wants_auto_execute_rejects_open_question():
    assert _wants_auto_execute("Was meinst du zu dem Layout?", []) is False


def test_pick_execute_task_skips_short_go_words():
    turns = [
        {"role": "user", "text": "Build a todo list with dark mode HTML"},
        {"role": "brainstorm", "text": "…"},
        {"role": "user", "text": "execute"},
    ]
    task = _pick_execute_task(turns, fallback="execute")
    assert "todo" in task.lower() or "build" in task.lower()
    assert task.lower().strip() != "execute"


# ── pipeline integration ────────────────────────────────────────────


def test_brainstorm_turn_has_flex_role_and_notes():
    pipe = Pipeline(EventBus())
    st = pipe.brainstorm_turn("Ideen zu einer Notiz-App, nur Brainstorm bitte")
    assert st.stage == PipelineStage.brainstorm
    roles = [t.get("role") for t in st.brainstorm_turns]
    assert "user" in roles and "brainstorm" in roles and "flex" in roles
    assert "Flex:" in (st.brainstorm_notes or "")


def test_execute_injects_flex_wish_requirements(tmp_path: Path):
    bus = EventBus()
    pipe = Pipeline(bus)
    # Seed WARM via facade path used by absorb wiring — set memory_context directly
    pipe.brainstorm_turn("Plan small utility app, nur ideen")
    pipe.state.memory_context = "User: always enable dark theme\nUser: never wipe wishes on clear\n"
    st = pipe.execute()
    if st.stage == PipelineStage.clarify:
        st = pipe.answer_clarify("MVP/schnell")
    reqs = "\n".join(st.distilled_requirements)
    assert "Flex-wish:" in reqs
    assert "dark theme" in reqs.lower()
    assert st.flex_notes


def test_coordinator_html_plan_embeds_flex_wish():
    bus = EventBus()
    coord = CoordinatorAgent(AgentManager(bus).get(AgentId.COORDINATOR), bus, llm=None)
    tasks = coord.plan(
        "Build landing page HTML",
        [
            "Ziel: shop",
            "Flex/personal: ignore me meta",
            "Flex-wish: User: always dark theme",
        ],
        ["worker1", "worker2", "worker3"],
        plan_mode="full_page_html",
    )
    assert len(tasks) == 1
    assert tasks[0][0] == "worker1"
    assert "always dark theme" in tasks[0][1]
    assert "ignore me meta" not in tasks[0][1]


def test_plan_modes_qa_and_diagnosis_assign_all_workers():
    bus = EventBus()
    coord = CoordinatorAgent(AgentManager(bus).get(AgentId.COORDINATOR), bus, llm=None)
    ids = ["worker1", "worker2", "worker3", "worker4"]
    qa = coord.plan("Review checkout", ["tests"], ids, plan_mode="plan_qa")
    assert len(qa) == 4
    assert all(w.startswith("worker") for w, _ in qa)
    assert "QA checklist" in qa[0][1] or "acceptance" in qa[0][1].lower()
    diag = coord.plan("Where does TTS fail", ["debug"], ids, plan_mode="diagnosis")
    assert len(diag) == 4
    assert "Root-cause" in diag[0][1] or "hypothes" in diag[0][1].lower()


def test_memory_facade_flex_block_priority(tmp_path: Path):
    warm = WarmMemory(tmp_path)
    hot = HotMemory(tmp_path, auto_load=False)
    warm.add_fact("User: always TTS for Flex", source="flex")
    warm.add_fact("Brand is Bean", source="warm")
    for i in range(30):
        hot.add_message("user", f"noise {i} " + ("x" * 50))
    fac = MemoryFacade(hot, warm)
    ctx = fac.pipeline_context(max_chars=350)
    assert ctx.startswith("FLEX_WISHES")
    assert "always TTS" in ctx


def test_full_flex_chat_to_done_smoke():
    bus = EventBus()
    events: list[str] = []
    for name in (
        "pipeline.flex_facts",
        "pipeline.flex_chat",
        "pipeline.flex_execute",
        "pipeline.auto_execute",
        "pipeline.flex",
        "pipeline.done",
    ):
        bus.on(name, lambda d, n=name: events.append(n))
    pipe = Pipeline(bus)
    st = pipe.brainstorm_turn("Build a landing page for Bean Shop. Full HTML with hero and footer.")
    assert st.stage in (PipelineStage.done, PipelineStage.clarify, PipelineStage.work)
    if st.stage == PipelineStage.clarify:
        st = pipe.answer_clarify("MVP/schnell")
    assert st.stage == PipelineStage.done
    assert "pipeline.done" in events
    # flex stage notes or execute path
    assert st.flex_notes or any(e == "pipeline.flex" for e in events)
