"""Send target routes never execute. START-IDs bind Ja. God is user-only."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app
from gnom_hub.core.event_bus import EventBus
from gnom_hub.flex_desk import FlexDesk
from gnom_hub.pipeline import Pipeline, PipelineStage
from gnom_hub.security.god_mode import GodMode, god_mode_from_env


def _isolate(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GNOM_WS", raising=False)
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "0")
    for key in list(os.environ):
        if key.endswith("_API_KEY") or key in ("DEEPSEEK_API_KEY", "WORKER_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None


def test_send_brainstorm_does_not_execute():
    pipe = Pipeline(EventBus())
    st = pipe.chat_turn("Baue eine komplette Landingpage HTML jetzt", target="brainstorm")
    assert st.stage != PipelineStage.done
    assert not st.worker_results
    assert st.mode != "execute" or st.stage in (
        PipelineStage.brainstorm,
        PipelineStage.clarify,
    )


def test_send_coordinator_does_not_execute():
    pipe = Pipeline(EventBus())
    st = pipe.chat_turn(
        "Auftrag: Datei README.md um eine Zeile ergänzen. DoD: Zeile sichtbar.",
        target="coordinator",
    )
    assert st.stage != PipelineStage.done
    assert not st.worker_results
    qs = pipe.flex_desk.open_questions()
    assert not st.worker_results
    assert qs or st.pending_question is not None


def test_send_worker_does_not_execute():
    pipe = Pipeline(EventBus())
    st = pipe.chat_turn("Prüfe nur tests/test_health.py und berichte.", target="worker1")
    assert st.stage != PipelineStage.done
    assert not st.worker_results


def test_send_worker_too_big_asks_flex_escalate():
    pipe = Pipeline(EventBus())
    st = pipe.chat_turn(
        "Bitte das ganze Projekt umbauen, alle Dateien, mehrere Worker, koordinieren.",
        target="worker1",
    )
    assert st.stage != PipelineStage.done
    qs = pipe.flex_desk.open_questions()
    assert qs
    assert any("Coordinator" in q.text for q in qs)


def test_unbound_yes_rejected_when_two_questions_open():
    desk = FlexDesk(job_id="job-a")
    a = desk.offer_start_work(job_id="job-a")
    b = desk.ask(
        agent_id="worker1",
        job_id="job-a",
        task_id="t1",
        text="Farbe dunkler?",
        component="yes_no",
    )
    assert a["ok"] and b["ok"]
    r = desk.answer(a["question_id"], "Ja", job_id="job-a")
    assert r["ok"] is False
    assert r["error"] == "unbound_yes"


def test_start_id_mismatch_does_not_start():
    desk = FlexDesk(job_id="job-a")
    asked = desk.offer_start_work(job_id="job-a")
    aid = asked.get("assignment_id") or ""
    assert aid.startswith("C")
    r = desk.answer(asked["question_id"], "Ja, START-C999 starten", job_id="job-a")
    assert r["ok"] is False or r.get("wants_start_work") is False


def test_matching_start_id_wants_start():
    desk = FlexDesk(job_id="job-a")
    asked = desk.offer_start_work(job_id="job-a")
    aid = asked["assignment_id"]
    r = desk.answer(asked["question_id"], f"Ja, START-{aid} starten", job_id="job-a")
    assert r["ok"] is True
    assert r["wants_start_work"] is True


def test_god_mode_rejects_agent_reason():
    gm = GodMode()
    with pytest.raises(PermissionError):
        gm.enable("flex")
    with pytest.raises(PermissionError):
        gm.enable("env:GNOM_GOD_MODE_AUTO")
    gm.enable("user", assignment_id="C1")
    assert gm.enabled is True
    assert gm.assignment_id == "C1"


def test_god_mode_env_does_not_auto_enable(monkeypatch):
    monkeypatch.setenv("GNOM_GOD_MODE_AUTO", "1")
    gm = god_mode_from_env()
    assert gm.enabled is False


def test_execute_status_is_delivered_not_accepted(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    h = hub_mod.Hub()
    try:
        h.pipeline.chat_turn("Baue eine Landingpage HTML", target="brainstorm")
        st = h.pipeline.execute()
        if st.stage.value == "clarify":
            st = h.pipeline.answer_clarify("Schnell und einfach")
        assert st.result_status != "ABGENOMMEN"
        assert st.result_status in (
            "GELIEFERT",
            "FEHLER",
            "UNGEPRÜFT",
            "TEILERGEBNIS",
        )
    finally:
        hub_mod._HUB = None


def test_api_chat_target_coordinator_stays_not_done(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/api/chat?sync=1",
            json={"text": "Fertiger Auftrag: README eine Zeile.", "target": "coordinator"},
        )
        assert r.status_code == 200
        p = r.json().get("pipeline") or {}
        assert p.get("stage") != "done"
        assert p.get("send_target") == "coordinator"
    hub_mod._HUB = None
