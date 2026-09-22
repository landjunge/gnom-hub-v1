"""V4 agent wiring: one conversation, real choices, Flex off the hot path."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gnom_hub.agents.roles import brainstorm_system_prompt
from gnom_hub.agents.roles_ext import CoordinatorAgent, _team_html_landing_plan
from gnom_hub.agents.roles_helpers import _lines, _needs_clarify
from gnom_hub.api.app import create_app
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.choices import (
    conversation_history,
    is_binding_standing_rule,
    parse_offered_choices,
)
from gnom_hub.pipeline.models import PipelineStage
from gnom_hub.pipeline.orchestrator import Pipeline


def test_brainstorm_prompt_does_not_send_users_to_flex():
    text = brainstorm_system_prompt("html_page")
    assert "Flex in Box 1" not in text
    assert "Arbeit starten ist der Button" in text


def test_coordinator_strips_meta_reasoning():
    raw = (
        "Let me think about this\n"
        "As Coordinator I should propose a plan\n"
        "Ziel: klare Landingpage\n"
        "Hero mit einem Satz Nutzen\n"
        "Eine echte Interaktion\n"
        "Vollständiges HTML bis </html>\n"
    )
    lines = _lines(raw)
    blob = " ".join(lines).lower()
    assert "let me think" not in blob
    assert "as coordinator" not in blob
    assert any("landingpage" in ln.lower() for ln in lines)
    assert 4 <= len(lines) <= 7


def test_confirmed_choice_skips_clarify():
    assert _needs_clarify("maybe dark mode?", confirmed=True) is False


def test_communication_pref_is_not_binding_worker_rule():
    assert is_binding_standing_rule("User: Erwartet knappe, minimale Antwort") is False
    assert is_binding_standing_rule("Flex-wish: User: always enable dark theme") is True


def test_parse_offered_choices_caps_at_four():
    text = "\n".join(
        [
            "A) Klarer und ruhiger",
            "B) Bunter und lauter",
            "C) Minimal ohne Schnickschnack",
            "D) Später entscheiden wir Details",
            "E) Extra fünfte Karte die weg muss",
        ]
    )
    cards = parse_offered_choices(text)
    assert len(cards) == 4
    assert cards[0]["id"] == "choice-a"


def test_conversation_prefers_messages():
    pipe = Pipeline(EventBus())
    pipe.state.messages = [
        {"role": "user", "visible_text": "Mach es klarer"},
        {"role": "brainstorm", "visible_text": "A) Klarer und ruhiger\nB) Bunter und lauter"},
    ]
    pipe.state.brainstorm_turns = [{"role": "user", "text": "alt"}]
    hist = conversation_history(pipe.state)
    assert hist[0]["text"] == "Mach es klarer"
    assert hist[1]["role"] == "brainstorm"


def test_choice_click_does_not_reask():
    pipe = Pipeline(EventBus())
    st = pipe.brainstorm_turn("Ich will eine Seite, schöner bitte")
    st.offered_choices = parse_offered_choices(
        "A) Klarer und ruhiger\nB) Bunter und lauter\nC) Minimal ohne Schnickschnack"
    )
    before = len(st.messages)
    st = pipe.confirm_choice("choice-a")
    assert st.confirmed_choices
    assert st.confirmed_choices[0]["id"] == "choice-a"
    assert st.pending_question is None
    assert st.stage == PipelineStage.brainstorm
    blob = " ".join(str(m.get("visible_text") or "") for m in st.messages[before:])
    assert "Verstanden" in blob
    assert "nicht nochmal" in blob.lower() or "Nicht nochmal" in blob
    # Second identical click must not spawn a coordinator question
    st2 = pipe.confirm_choice("choice-a")
    assert st2.pending_question is None
    assert len(st2.confirmed_choices) == 1


def test_ja_binds_to_last_offered_choice():
    pipe = Pipeline(EventBus())
    pipe.brainstorm_turn("Seite soll klarer werden")
    pipe.state.offered_choices = parse_offered_choices(
        "A) Klarer und ruhiger\nB) Bunter und lauter"
    )
    st = pipe.brainstorm_turn("ja")
    assert st.confirmed_choices
    assert "Klarer" in str(st.confirmed_choices[0].get("title") or "")


def test_brainstorm_does_not_wipe_worker_results():
    pipe = Pipeline(EventBus())
    pipe.brainstorm_turn("Landingpage")
    pipe.state.worker_results = ["<!DOCTYPE html><html></html>"]
    pipe.state.worker_outputs = [{"worker": "worker1", "result": "<html></html>"}]
    pipe.brainstorm_turn("noch ein Gedanke dazu")
    assert pipe.state.worker_results
    assert pipe.state.worker_outputs


def test_execute_skips_flex_personal_requirement():
    pipe = Pipeline(EventBus())
    pipe.brainstorm_turn("Build a landing page for Bean Shop full HTML")
    pipe.state.memory_context = (
        "User: Erwartet knappe, minimale Antwort\nUser: always enable dark theme\n"
    )
    st = pipe.execute()
    if st.stage == PipelineStage.clarify:
        st = pipe.answer_clarify("Schnell und einfach")
    reqs = "\n".join(st.distilled_requirements)
    assert "Flex/personal:" not in reqs
    assert "knappe" not in reqs.lower()
    assert "dark theme" in reqs.lower()


def test_team_html_plan_uses_all_four_workers():
    tasks = _team_html_landing_plan(
        "Bean Shop",
        ["worker1", "worker2", "worker3", "worker4"],
        ["Ziel: Shop"],
    )
    assert [w for w, _ in tasks] == ["worker1", "worker2", "worker3", "worker4"]


def test_coordinator_distill_skips_after_choice():
    bus = EventBus()
    from gnom_hub.agents import AgentId, AgentManager

    coord = CoordinatorAgent(AgentManager(bus).get(AgentId.COORDINATOR), bus, llm=None)
    reqs, question = coord.distill(
        "maybe a cooler page",
        "A) Klarer\nB) Bunter",
        confirmed=True,
    )
    assert question is None
    assert 4 <= len(reqs) <= 7


def test_v4_choice_endpoint_and_prompt_copy():
    app = create_app()
    with TestClient(app) as client:
        js = client.get("/static/v4.js").text
        html = client.get("/v4").text
        client.post(
            "/api/chat?sync=true", json={"text": "Mach die Seite klarer", "target": "brainstorm"}
        )
        res = client.post(
            "/api/choice?sync=true",
            json={
                "id": "choice-a",
                "title": "Klarer und ruhiger",
                "effect": "Mehr Lesbarkeit, weniger Technik.",
                "value": "Klarer und ruhiger",
            },
        )
    assert res.status_code == 200
    pipe = res.json()["pipeline"]
    assert pipe["confirmed_choices"]
    assert pipe["confirmed_choices"][0]["id"] == "choice-a"
    assert "/api/choice" in js
    assert "Flex" not in html
    assert "Arbeit starten" in html
