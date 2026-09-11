"""Brainstorm is a dialogue partner, not a mini-Execute."""

from __future__ import annotations

from gnom_hub.agents.chat_policy import brainstorm_system_extra
from gnom_hub.agents.roles import brainstorm_system_prompt
from gnom_hub.agents.roles_helpers import _stub_brainstorm
from gnom_hub.core.event_bus import EventBus
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec
from gnom_hub.tools.worker_prefetch import prefetch_for_brainstorm


def _banned(text: str) -> None:
    low = text.lower()
    assert "soll ich das jetzt umsetzen" not in low
    assert "hub startet" not in low
    assert "pipeline auto-executes" not in low
    assert "hub executes" not in low


def test_brainstorm_prompt_is_dialogue_not_execute():
    p = brainstorm_system_prompt("general")
    _banned(p)
    assert "mitdenken" in p.lower() or "denkpartner" in p.lower()
    assert "box 1" in p.lower() or "flex" in p.lower()
    html = brainstorm_system_prompt("html_page")
    _banned(html)
    assert "anbieten die arbeit zu starten" in p.lower() or "box 1" in p.lower()


def test_brainstorm_stub_does_not_claim_pipeline_starts():
    out = _stub_brainstorm("Build a landing page", [])
    _banned(out)
    out2 = _stub_brainstorm("ich will eine geile webseite", [])
    _banned(out2)
    assert "geil" in out2.lower() or "richtung" in out2.lower() or "optisch" in out2.lower()


def test_brainstorm_policy_html_does_not_say_hub_executes():
    extra = brainstorm_system_extra("html_page")
    _banned(extra)
    extra_d = brainstorm_system_extra("tool_drill")
    _banned(extra_d)


def test_prefetch_for_brainstorm_sparks_on_vague_site(monkeypatch):
    bus = EventBus()
    tools = ToolRegistry()

    def search(query: str = "", count: int = 3, **_k):
        return {
            "ok": True,
            "query": query,
            "hits": [{"title": "Awwwards", "url": "https://www.awwwards.com", "snippet": "laut"}],
        }

    tools.register(ToolSpec(name="web_search", description="s", handler=search, plugin="web"))
    ctx = prefetch_for_brainstorm(
        "ich will eine geile webseite",
        bus=bus,
        tools=tools,
        memory=None,
    )
    assert "Tool prefetch" in ctx or "web_search" in ctx or "awwwards" in ctx.lower()
