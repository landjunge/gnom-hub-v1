"""Standing wishes are absolute orders — DoD + Flex note learn."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.agents.manager import AgentManager
from gnom_hub.agents.models import AgentId
from gnom_hub.agents.roles_ext import CoordinatorAgent
from gnom_hub.api.app import create_app
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.orchestrator import _definition_of_done


def test_definition_of_done_marks_wishes_absolute():
    dod = _definition_of_done(
        "Landing page",
        [
            "Ziel: Café",
            "Flex-wish: User: always enable dark theme",
            "User: prefers German language answers",
        ],
    )
    assert "ABSOLUTE" in dod
    assert "always enable dark theme" in dod
    assert "[!]" in dod


def test_html_plan_embeds_wish():
    bus = EventBus()
    coord = CoordinatorAgent(AgentManager(bus).get(AgentId.COORDINATOR), bus, llm=None)
    tasks = coord.plan(
        "Build a landing page HTML",
        ["Flex-wish: User: always enable dark theme", "Ziel: shop"],
        ["worker1"],
        plan_mode="full_page_html",
    )
    assert "always enable dark theme" in tasks[0][1]


def test_flex_custom_note_learns(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    (tmp_path / "User").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GNOM_USER_DB", str(tmp_path / "User" / "user.db"))
    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/api/flex/feedback",
            json={
                "button_id": "custom_note",
                "label": "Notiz",
                "note": "immer dunkles Theme",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("learned") is True
        learn = str(body.get("learn_text") or "").lower()
        assert "dunk" in learn or "theme" in learn or "immer" in learn
    hub_mod._HUB = None
