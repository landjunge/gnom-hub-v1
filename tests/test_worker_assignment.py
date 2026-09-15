"""Send-flag assignment: Arbeit starten uses the chosen worker, not always Worker 1."""

from gnom_hub.agents.roles_ext import _html_full_page_plan
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.orchestrator import Orchestrator


def test_html_plan_follows_reordered_worker_ids():
    tasks = _html_full_page_plan(
        "Landing page",
        ["worker3", "worker1", "worker2"],
        ["Dark theme"],
    )
    assert len(tasks) == 1
    assert tasks[0][0] == "worker3"


def test_flagged_worker_is_first_for_plan():
    orch = Orchestrator(EventBus())
    orch.state.send_target = "worker2"
    ids = orch._worker_ids_for_plan()
    assert ids[0] == "worker2"
    assert "worker1" in ids
    assert ids == ["worker2"] + [w for w in ids if w != "worker2"]


def test_brainstorm_flag_keeps_default_order():
    orch = Orchestrator(EventBus())
    orch.state.send_target = "brainstorm"
    ids = orch._worker_ids_for_plan()
    assert ids[0] == "worker1"


def test_worker_intake_keeps_assignment():
    orch = Orchestrator(EventBus())
    st = orch.chat_turn("Baue eine ruhige Abendseite", target="worker3")
    assert st.send_target == "worker3"
    assert "worker3" in (st.messages[-1].get("visible_text") or "")
    assert "zugeteilt" in (st.messages[-1].get("visible_text") or "").lower()
    ids = orch._worker_ids_for_plan()
    assert ids[0] == "worker3"
