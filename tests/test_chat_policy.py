"""Chat routing policy — tool drill / browser / HTML / go-only."""

from __future__ import annotations

from gnom_hub.agents.chat_policy import (
    brainstorm_system_extra,
    coordinator_distill_system,
    task_kind,
)
from gnom_hub.agents.roles_ext import _html_full_page_plan


def test_task_kind_tool_drill():
    assert task_kind("Tool drill S7 killer") == "tool_drill"
    assert task_kind("installiere playwright und teste") == "tool_drill"


def test_task_kind_browser_nav():
    assert task_kind("navigiere zu https://www.kleinanzeigen.de") == "browser_nav"
    assert task_kind("kleinanzeigen") != "browser_nav"
    assert task_kind("https://example.com") == "browser_nav"


def test_task_kind_html_not_browser_when_fetch_for_page():
    assert task_kind("Need https://example.org/x for the page") != "browser_nav"
    # page-like may be html_page or general depending on keywords
    k = task_kind("Baue eine Landingpage HTML für Gnom-Hub")
    assert k == "html_page"


def test_task_kind_go_only():
    assert task_kind("mach das was ich gesagt habe") == "go_only"
    assert task_kind("execute") == "go_only"


def test_task_kind_diagnose():
    assert task_kind("wo hakt es? bug debug") == "diagnose"


def test_brainstorm_html_is_dialogue_not_worker_plan():
    """Brainstorm riffs in Box 2. One-worker HTML is Coordinator plan, not this extra."""
    extra = brainstorm_system_extra("html_page")
    low = extra.lower()
    assert "mitdenken" in low
    assert "kein code" in low or "kein execute" in low
    assert "box 1" in low
    assert "one worker" not in low
    assert "multi-worker" not in low


def test_html_full_page_plan_is_one_worker():
    plan = _html_full_page_plan("Landingpage", ["worker1", "worker2"], ["DoD"])
    assert len(plan) == 1
    assert plan[0][0] == "worker1"
    assert "ONE complete" in plan[0][1] or "</html>" in plan[0][1]
    dist = coordinator_distill_system("html_page")
    assert "</html>" in dist or "html" in dist.lower()
