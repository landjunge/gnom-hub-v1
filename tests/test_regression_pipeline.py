"""Offline regression suite for multi-agent pipeline contracts.

No live LLM / server required. Runs in CI via pytest.
Scenarios encode evaluation DoD from pipeline design:
  - fast-path plan mode
  - HTML gates
  - clarify / no-auto-execute heuristics
  - stage timing helpers
  - flex wish filter contracts (import existing)
"""

from __future__ import annotations

import pytest

from gnom_hub.agents.plan_fast_path import resolve_plan_mode
from gnom_hub.agents.roles_ext import _html_full_page_plan
from gnom_hub.agents.roles_helpers import _needs_clarify
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.models import PipelineStage, PipelineState
from gnom_hub.pipeline.orchestrator import (
    Orchestrator,
    _has_interaction,
    _html_complete,
    _wants_auto_execute,
)

# ── R1: Plan fast-path ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,reqs,expect_fast",
    [
        ("Build a landing page for Bean & Bloom coffee", None, True),
        ("Todo app", ["Single-file HTML UI"], True),
        ("Portfolio website dark theme", None, True),
        ("design the database schema only", None, False),
        ("multi-page documentation site", None, False),
        ("backend only REST API", None, False),
    ],
)
def test_r1_fast_path_resolution(text, reqs, expect_fast):
    mode, fast = resolve_plan_mode("default", text, reqs)
    if expect_fast:
        assert mode == "full_page_html" and fast is True
    else:
        assert fast is False
        assert mode == "default"


def test_r1_html_plan_single_worker():
    tasks = _html_full_page_plan(
        "Landing page",
        ["worker1", "worker2", "worker3"],
        ["Hero", "CTA"],
    )
    assert len(tasks) == 1
    assert tasks[0][0] == "worker1"
    assert "ONE complete" in tasks[0][1]


# ── R2: Clarify / auto-execute gates ────────────────────────────────


def test_r2_clarify_vague():
    assert _needs_clarify(
        "Maybe build something cool with dark mode, not sure yet",
        "",
    )


def test_r2_no_auto_execute_pure_question():
    assert not _wants_auto_execute("What could TTS do inside Gnom-Hub?")


def test_r2_auto_execute_clear_build():
    assert _wants_auto_execute("Build a modern landing page for a coffee shop called Bean & Bloom")


# ── R3: HTML quality gates ──────────────────────────────────────────

COMPLETE_HTML = """<!DOCTYPE html>
<html><head><title>x</title></head>
<body>
<button onclick=\"alert(1)\">Go</button>
</body></html>
"""


def test_r3_html_complete_and_interaction():
    assert _html_complete(COMPLETE_HTML)
    assert _has_interaction(COMPLETE_HTML)


def test_r3_html_incomplete():
    assert not _html_complete("<html><body>no close")
    assert not _html_complete("")


# ── R4: Stage timing helpers ────────────────────────────────────────


def test_r4_stage_timing_records_ms():
    bus = EventBus()
    events: list[dict] = []
    bus.on("pipeline.stage_timing", lambda d: events.append(d))
    orch = Orchestrator(bus)
    orch._begin_stage_timing("distill")
    orch._close_stage_timing()
    assert "distill" in orch.state.stage_timings
    assert orch.state.stage_timings["distill"] >= 0
    assert events and events[0]["stage"] == "distill"


def test_r4_clarify_does_not_time_user_wait():
    bus = EventBus()
    orch = Orchestrator(bus)
    orch._begin_stage_timing("distill")
    orch._set_stage(PipelineStage.clarify)
    assert orch._stage_t0 is None
    assert "distill" in orch.state.stage_timings


def test_r4_pipeline_state_fields():
    st = PipelineState()
    assert st.stage_timings == {}
    assert st.resolved_plan_mode == ""


# ── R5: Coordinator plan meta (stub, no LLM) ────────────────────────


def test_r5_coordinator_sets_last_plan_meta():
    bus = EventBus()
    orch = Orchestrator(bus)
    tasks = orch.coordinator.plan(
        "Build a landing page for Bean Bloom",
        ["Hero section", "CTA button"],
        ["worker1", "worker2"],
        plan_mode="default",
    )
    meta = getattr(orch.coordinator, "last_plan_meta", {})
    assert meta.get("plan_mode") == "full_page_html"
    assert meta.get("fast_path") is True
    assert len(tasks) == 1
