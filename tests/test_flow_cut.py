"""Send = talk. Arbeit starten = result. Box 1 = Passt das? No START-C1."""

from gnom_hub.core.event_bus import EventBus
from gnom_hub.flex_desk import FlexDesk
from gnom_hub.pipeline.orchestrator import Orchestrator


def test_send_does_not_open_start_c1():
    orch = Orchestrator(EventBus())
    st = orch.chat_turn("Baue eine Landing Page")
    qs = [q for q in orch.flex_desk.open_questions() if q.component == "start_work"]
    assert qs == []
    blob = " ".join(str(t.get("text") or "") for t in (st.brainstorm_turns or []))
    assert "START-" not in blob
    assert not any(t.get("role") == "flex" for t in (st.brainstorm_turns or []))


def test_send_build_language_does_not_start_workers():
    orch = Orchestrator(EventBus())
    st = orch.chat_turn(
        "Build a modern landing page for a coffee shop called Bean & Bloom. Full HTML."
    )
    assert st.stage.value == "brainstorm"
    assert not st.worker_results
    assert not st.worker_outputs


def test_send_tool_drill_does_not_finish_pipeline():
    orch = Orchestrator(EventBus())
    st = orch.chat_turn("Tool drill S6 plugins")
    assert st.stage.value != "done"
    assert not st.worker_results


def test_go_only_after_task_does_not_start_workers():
    orch = Orchestrator(EventBus())
    orch.chat_turn("Ideen zu einer Checklisten-App, nur Brainstorm bitte")
    st = orch.chat_turn("mach das")
    assert st.stage.value == "brainstorm"
    assert not st.worker_results


def test_judgment_question_after_finish_with_results():
    desk = FlexDesk()
    out = desk.offer_judgment()
    assert out["ok"] is True
    assert out["component"] == "judgment"
    assert out["text"] == "Passt das?"
    assert out["options"] == ["Gut", "Verfeinern", "Fertig"]
    assert "START-" not in out["text"]
