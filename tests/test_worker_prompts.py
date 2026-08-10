"""Worker prompt layers + design prefetch detection."""

from __future__ import annotations

from gnom_hub.agents.roles_workers import task_wants_html, worker_system_prompt
from gnom_hub.core.event_bus import EventBus
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.tools.worker_prefetch import (
    prefetch_for_workers,
    tool_calls_needed,
    wants_design_tools,
)


def test_task_wants_html_keywords():
    assert task_wants_html("Build a landing page")
    assert task_wants_html("HTML Seite mit Formular")
    assert not task_wants_html("summarize this PDF")


def test_worker_system_prompt_layers():
    base = worker_system_prompt(wants_html=False)
    assert "TOOL PROTOCOL" in base
    assert "ABSOLUTE ORDERS" in base
    assert "ONE complete file" not in base  # HTML domain layer off

    html = worker_system_prompt(wants_html=True)
    assert "ONE complete file" in html
    assert "Do NOT invent a second palette" in html
    assert "html_scaffold" in html


def test_tool_calls_needed_design():
    need = tool_calls_needed("Build HTML landing page dark theme")
    assert "color_palette" in need
    assert "html_scaffold" in need
    assert "memory_search" in need
    assert wants_design_tools("website redesign")


def test_prefetch_design_tools_via_registry():
    bus = EventBus()
    events: list[dict] = []
    bus.on("pipeline.tool_call", lambda d: events.append(d if isinstance(d, dict) else {}))

    tools = ToolRegistry()

    def palette(seed: str = "dark", count: int = 5):
        return {
            "ok": True,
            "primary": "#5b8def",
            "accent": "#7c3aed",
            "surface": "#0f172a",
            "text": "#e6edf3",
            "css": ":root { --color-primary: #5b8def; }\n",
        }

    def scaffold(kind: str = "landing", title: str = "Page", seed: str = "dark"):
        return {
            "ok": True,
            "kind": kind,
            "html": "<!DOCTYPE html><html><body>scaffold</body></html>",
        }

    def contrast(fg: str = "", bg: str = ""):
        return {"ok": True, "ratio": 12.0, "grade": "AAA", "aa_normal": True}

    tools.register(ToolSpec(name="color_palette", description="p", handler=palette, plugin="web_design"))
    tools.register(ToolSpec(name="html_scaffold", description="s", handler=scaffold, plugin="web_design"))
    tools.register(ToolSpec(name="contrast_check", description="c", handler=contrast, plugin="web_design"))

    ctx = prefetch_for_workers(
        "Build HTML landing page for ocean brand",
        bus=bus,
        tools=tools,
        memory=None,
    )
    assert "color_palette" in ctx
    assert "--color-primary" in ctx or "primary=" in ctx
    assert "html_scaffold" in ctx
    assert "scaffold" in ctx
    names = [e.get("name") for e in events]
    assert "color_palette" in names
    assert "html_scaffold" in names
    assert "contrast_check" in names
