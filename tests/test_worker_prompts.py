"""Worker prompt layers + design prefetch detection."""

from __future__ import annotations

from gnom_hub.agents.models import AgentId, AgentState
from gnom_hub.agents.roles_workers import WorkerAgent, task_wants_html, worker_system_prompt
from gnom_hub.core.event_bus import EventBus
from gnom_hub.llm.types import LLMResult
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
    assert "FLEX_ASK" in base
    assert "do not guess" in base.lower()
    assert "yes_no" in base
    assert "FEHLER" in base

    html = worker_system_prompt(wants_html=True)
    assert "ONE complete file" in html
    assert "Do NOT invent a second palette" in html
    assert "html_scaffold" in html
    assert "FLEX_ASK" in html


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

    tools.register(
        ToolSpec(name="color_palette", description="p", handler=palette, plugin="web_design")
    )
    tools.register(
        ToolSpec(name="html_scaffold", description="s", handler=scaffold, plugin="web_design")
    )
    tools.register(
        ToolSpec(name="contrast_check", description="c", handler=contrast, plugin="web_design")
    )

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


def _worker_state() -> AgentState:
    return AgentState(
        id=AgentId.WORKER1,
        name="Worker 1",
        role="worker",
        color="cyan",
        enabled=True,
        toggleable=True,
    )


class _RecordingLLM:
    """Captures system prompts actually sent to chat()."""

    def __init__(self, reply: str = "ok") -> None:
        self.reply = reply
        self.system_prompts: list[str] = []

    def has_provider(self, name: str = "deepseek") -> bool:
        return True

    def chat(self, messages, **kwargs):
        for m in messages:
            if getattr(m, "role", "") == "system":
                self.system_prompts.append(str(getattr(m, "content", "") or ""))
        return LLMResult(content=self.reply, model="fake")


def test_worker_run_sends_flex_ask_in_system_prompt():
    """L1 FLEX_ASK is not just a constant — it reaches BaseAgent.ask as system."""
    bus = EventBus()
    llm = _RecordingLLM(reply="checklist draft")
    w = WorkerAgent(_worker_state(), bus, llm=llm)
    out = w.run(
        "Write a short onboarding checklist",
        "I need an onboarding checklist",
        ["clear steps"],
    )
    assert out == "checklist draft"
    assert llm.system_prompts
    joined = "\n".join(llm.system_prompts)
    assert "FLEX_ASK" in joined
    assert "do not guess" in joined.lower()


def test_worker_tool_loop_keeps_flex_ask_in_system():
    """run_tool_loop must forward the worker system prompt, not drop L1."""
    bus = EventBus()
    llm = _RecordingLLM(reply="done")
    tools = ToolRegistry()
    tools.register(
        ToolSpec(name="web_fetch", description="fetch a URL", handler=lambda **_k: {"ok": True})
    )
    w = WorkerAgent(_worker_state(), bus, llm=llm, tools=tools)
    out = w.run(
        "Write a short onboarding checklist",
        "I need an onboarding checklist",
        ["clear steps"],
    )
    assert out == "done"
    assert llm.system_prompts
    joined = "\n".join(llm.system_prompts)
    assert "FLEX_ASK" in joined
    assert "do not guess" in joined.lower()
