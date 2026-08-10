"""Plan-mode fast path + scoring heuristic tests."""

from __future__ import annotations

import pytest

from gnom_hub.agents.plan_fast_path import (
    _html_page_score,
    _wants_one_html_page,
    resolve_plan_mode,
)
from gnom_hub.agents.roles_ext import _html_full_page_plan
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.models import PipelineStage, PipelineState
from gnom_hub.pipeline.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Bestehende Verträge
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Scoring – parametrisierte Edge Cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "user_text, requirements, min_score, max_score, label",
    [
        # Leere / triviale
        ("", None, 0, 0, "empty"),
        ("   ", None, 0, 0, "whitespace"),
        ("\n\n", None, 0, 0, "newlines"),

        # Schwache Signale
        ("page", None, 0, 2, "isolated page"),
        ("seite", None, 0, 2, "isolated seite"),
        ("auf der seite stehen lassen", None, 0, 2, "seite context negative"),
        ("config page", None, 0, 2, "config page"),
        ("settings page", None, 0, 2, "settings page"),
        ("page 12", None, 0, 2, "page number"),
        ("frontend", None, 0, 2, "isolated frontend"),
        ("ui", None, 0, 2, "isolated ui"),

        # Starke Positive
        ("Build a landing page", None, 3, 99, "classic landing"),
        ("single-file HTML", None, 3, 99, "single-file"),
        ("Erstelle eine Seite mit Hero", None, 3, 99, "DE hero"),
        ("mach mir eine seite", None, 3, 99, "DE natural"),
        ("Portfolio website dark theme", None, 3, 99, "portfolio"),
        ("Todo app", ["Single-file HTML UI with localStorage"], 3, 99, "req saves weak"),
        ("startseite bauen", None, 3, 99, "DE startseite"),
        ("Landing-Page", None, 3, 99, "hyphen"),
        ("landingpage", None, 3, 99, "compound"),
        ("SPA dashboard", None, 3, 99, "SPA + dashboard"),
        ("html datei", None, 3, 99, "html datei"),

        # Starke Negative
        ("multi-page documentation", None, 0, 0, "multi-page"),
        ("mehrere seiten", None, 0, 0, "DE multi"),
        ("backend only REST API", None, 0, 0, "backend only"),
        ("database schema only", None, 0, 0, "schema only"),
        ("cli tool", None, 0, 0, "cli"),
        ("playwright test", None, 0, 0, "playwright"),
        ("navigiere zu https://www.kleinanzeigen.de", None, 0, 0, "live browser"),
        ("öffne https://example.com", None, 0, 0, "open https"),
        ("tools testen", None, 0, 0, "tools testen"),
        ("Tool drill S7 killer", None, 0, 0, "tool drill"),

        # Gemischte Signale
        ("landing page aber multi-page", None, 0, 2, "pos+neg multi"),
        ("HTML Seite und REST API only", None, 0, 2, "pos+neg api"),
        ("website bauen und backend only", None, 0, 2, "pos+neg backend"),

        # Requirements-Einfluss
        ("mach was", ["Single-file HTML"], 3, 99, "req rescues"),
        ("mach was", ["REST API only"], 0, 2, "req negative"),
        ("Landing page", ["backend only"], 0, 2, "req overrides"),
    ],
)
def test_html_page_score_range(
    user_text: str,
    requirements: list[str] | None,
    min_score: int,
    max_score: int,
    label: str,
):
    score = _html_page_score(user_text, requirements)
    assert min_score <= score <= max_score, (
        f"[{label}] score={score} not in [{min_score},{max_score}] "
        f"text={user_text!r} reqs={requirements}"
    )


@pytest.mark.parametrize(
    "user_text, requirements, expected",
    [
        ("Build a landing page for Bean Bloom", None, True),
        ("single-file HTML dashboard", None, True),
        ("Erstelle eine Seite mit Hero und Footer", None, True),
        ("mach mir eine seite", None, True),
        ("Portfolio website, dark theme", None, True),
        ("Todo app", ["Single-file HTML UI with localStorage"], True),
        ("startseite bauen", None, True),
        ("zeig mir eine ui für das dashboard", None, True),
        ("", None, False),
        ("page", None, False),
        ("seite", None, False),
        ("auf der seite stehen lassen", None, False),
        ("config page", None, False),
        ("design the database schema only", None, False),
        ("multi-page documentation site", None, False),
        ("backend only REST API", None, False),
        ("navigiere zu https://www.kleinanzeigen.de", None, False),
        ("Tool drill S7 killer", None, False),
        ("playwright test und screenshot", None, False),
        ("landing page aber multi-page", None, False),
        ("mach was", ["REST API only"], False),
    ],
)
def test_wants_one_html_page_boolean(
    user_text: str,
    requirements: list[str] | None,
    expected: bool,
):
    assert _wants_one_html_page(user_text, requirements) is expected


@pytest.mark.parametrize(
    "plan_mode, user_text, expected_mode, expected_fast",
    [
        ("default", "Landing page coffee shop", "full_page_html", True),
        ("default", "mach mir eine seite mit hero", "full_page_html", True),
        ("default", "single-file HTML portfolio", "full_page_html", True),
        ("default", "analysiere den code", "default", False),
        ("default", "auf der seite stehen lassen", "default", False),
        ("default", "page", "default", False),
        ("default", "Tool drill S7 killer", "default", False),
        ("default", "navigiere zu https://www.kleinanzeigen.de", "default", False),
        ("default", "öffne https://example.com", "default", False),
        ("full_page_html", "anything", "full_page_html", True),
        ("plan_qa", "Landing page", "plan_qa", False),
        ("diagnosis", "Landing page", "diagnosis", False),
        ("team", "Landing page", "team", False),
    ],
)
def test_resolve_plan_mode_parametrized(
    plan_mode: str,
    user_text: str,
    expected_mode: str,
    expected_fast: bool,
):
    mode, fast = resolve_plan_mode(plan_mode, user_text)
    assert mode == expected_mode
    assert fast is expected_fast


def test_score_never_negative():
    cases = [
        "multi-page backend only api only cli tool playwright",
        "tool drill live browser navigiere zu öffne https",
        "mehrere seiten und REST API only",
    ]
    for text in cases:
        assert _html_page_score(text) >= 0


def test_score_empty_requirements_safe():
    assert _html_page_score("Build a landing page", None) >= 3
    assert _html_page_score("Build a landing page", []) >= 3
    assert _html_page_score("Build a landing page", [""]) >= 3
