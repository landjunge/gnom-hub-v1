"""Flex nudge: worker_error gets message; auth errors do not burn a useless re-run."""

from __future__ import annotations

from gnom_hub.agents.models import AgentId, AgentState
from gnom_hub.agents.roles import FlexAgent
from gnom_hub.core.event_bus import EventBus


def _flex() -> FlexAgent:
    st = AgentState(
        id=AgentId.FLEX,
        name="Flex",
        role="flex",
        color="yellow",
        enabled=True,
        toggleable=True,
    )
    return FlexAgent(st, EventBus(), llm=None)


def test_heuristic_nudge_on_worker_error():
    flex = _flex()
    outs = [
        {
            "worker": "worker1",
            "result": "Worker 1 FEHLER - kein Deliverable\nKey missing",
            "validation": {"ok": False, "issues": ["worker_error"]},
        }
    ]
    nudges = flex.nudge_gaps("landing html", ["hero"], outs, quality_notes="Gates failed")
    assert nudges
    assert any(
        "Key" in n.get("message", "") or "Deliverable" in n.get("message", "") for n in nudges
    )
    assert nudges[0]["agent"] == "worker1"


def test_flex_nudge_skips_rerun_on_auth_error():
    """Orchestrator path: worker_error outputs stay, no second run required for test of heuristic."""
    flex = _flex()
    body = "Worker 1 FEHLER - kein Deliverable\nAuthentifizierung fehlgeschlagen"
    outs = [
        {
            "worker": "worker1",
            "result": body,
            "task": "page",
            "validation": {"ok": False, "issues": ["worker_error", "incomplete_html"]},
        }
    ]
    n = flex._heuristic_nudges("html", [], outs, "")
    assert any(x["reason"] == "quality_gap" for x in n)
