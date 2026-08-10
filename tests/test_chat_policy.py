"""Chat routing policy — tool drill / browser / HTML / go-only."""

from __future__ import annotations

from gnom_hub.agents.chat_policy import brainstorm_system_extra, task_kind


def test_task_kind_tool_drill():
    assert task_kind("Tool drill S7 killer") == "tool_drill"
    assert task_kind("installiere playwright und teste") == "tool_drill"


def test_task_kind_browser_nav():
    assert task_kind("navigiere zu https://www.kleinanzeigen.de") == "browser_nav"
    assert task_kind("kleinanzeigen") == "browser_nav"
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


def test_brainstorm_html_one_worker_not_multi():
    extra = brainstorm_system_extra("html_page")
    assert "ONE worker" in extra or "one worker" in extra.lower()
    assert "multi half" in extra.lower() or "ONE complete" in extra
    assert "multi-worker team" not in extra.lower()
