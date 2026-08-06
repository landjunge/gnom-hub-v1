"""Plan-mode fast path + stage timing contracts."""

from __future__ import annotations

from gnom_hub.agents.plan_fast_path import _wants_one_html_page, resolve_plan_mode
from gnom_hub.agents.roles_ext import _html_full_page_plan
# Re-export path also works via roles_ext after import wiring
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.models import PipelineStage, PipelineState
from gnom_hub.pipeline.orchestrator import Orchestrator


def test_wants_one_html_page_positives():
    assert _wants_one_html_page("Build a landing page for Bean Bloom")
    assert _wants_one_html_page("Portfolio website, dark theme")
    assert _wants_one_html_page("Todo app", ["Single-file HTML UI with localStorage"])
    assert _wants_one_html_page("Erstelle eine Seite mit Hero und Footer")


def test_wants_one_html_page_negatives():
    assert not _wants_one_html_page("design the database schema only")
    assert not _wants_one_html_page("multi-page documentation site")
    assert not _wants_one_html_page("backend only REST API")
    assert not _wants_one_html_page("auf der seite stehen lassen")


def test_resolve_plan_mode_default_upgrades():
    mode, fast = resolve_plan_mode("default", "Landing page coffee shop")
    assert mode == "full_page_html"
    assert fast is True


def test_resolve_plan_mode_explicit_preserved():
    mode, fast = resolve_plan_mode("plan_qa", "Landing page")
    assert mode == "plan_qa"
    assert fast is False
    mode2, fast2 = resolve_plan_mode("full_page_html", "anything")
    assert mode2 == "full_page_html"
    assert fast2 is True


def test_html_full_page_plan_single_worker():
    tasks = _html_full_page_plan(
        "Landing page",
        ["worker1", "worker2", "worker3"],
        ["Dark theme", "Hero section"],
    )
    assert len(tasks) == 1
    assert tasks[0][0] == "worker1"
    assert "ONE complete" in tasks[0][1]
    assert "Dark theme" in tasks[0][1]


def test_stage_timings_helpers_accumulate():
    bus = EventBus()
    seen: list[dict] = []
    bus.on("pipeline.stage_timing", lambda d: seen.append(d))
    orch = Orchestrator(bus)
    orch._begin_stage_timing("distill")
    orch._close_stage_timing()
    assert "distill" in orch.state.stage_timings
    assert orch.state.stage_timings["distill"] >= 0
    assert seen and seen[0]["stage"] == "distill"


def test_set_stage_does_not_time_clarify_wait():
    bus = EventBus()
    orch = Orchestrator(bus)
    orch._begin_stage_timing("distill")
    orch._set_stage(PipelineStage.clarify)
    assert orch._stage_t0 is None
    assert "distill" in orch.state.stage_timings


def test_pipeline_state_has_timing_fields():
    st = PipelineState()
    assert st.stage_timings == {}
    assert st.resolved_plan_mode == ""
