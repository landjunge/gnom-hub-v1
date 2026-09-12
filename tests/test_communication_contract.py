"""Communication contract: IDs, routing, no silent fallback, Send ≠ execute."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gnom_hub.api.app import create_app
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline import Pipeline, PipelineStage
from gnom_hub.pipeline.orchestrator import ALLOWED_SEND_TARGETS


def _agent_replies(st, agent: str) -> list[dict]:
    msgs = list(getattr(st, "messages", None) or [])
    return [m for m in msgs if m.get("role") == "agent" and m.get("reply_agent_id") == agent]


def test_coordinator_send_has_visible_coordinator_reply():
    pipe = Pipeline(EventBus())
    st = pipe.chat_turn("AUDIT: nur PONG, keine Dateien.", target="coordinator")
    assert st.stage != PipelineStage.done
    assert not st.worker_outputs
    replies = _agent_replies(st, "coordinator")
    assert replies, "Coordinator must produce a visible agent reply"
    last = replies[-1]
    assert last.get("visible_text")
    assert last.get("reply_id")
    assert last.get("conversation_id") == "conv-coordinator"
    assert last.get("in_reply_to")
    assert last.get("source") in ("live", "template", "fallback")
    if last.get("source") in ("template", "fallback"):
        assert last.get("status") in ("template", "fallback", "replied")


def test_brainstorm_send_has_ids_and_no_workers():
    pipe = Pipeline(EventBus())
    st = pipe.chat_turn("AUDIT-BS: sag PONG.", target="brainstorm")
    assert not st.worker_outputs
    users = [
        m
        for m in (st.messages or [])
        if m.get("role") == "user" and m.get("target_agent_id") == "brainstorm"
    ]
    assert users
    assert users[-1]["message_id"]
    replies = _agent_replies(st, "brainstorm")
    assert replies
    assert replies[-1]["reply_agent_id"] == "brainstorm"


def test_worker_send_replies_without_execute():
    pipe = Pipeline(EventBus())
    st = pipe.chat_turn("Prüfe nur tests/test_health.py und berichte.", target="worker1")
    assert st.stage != PipelineStage.done
    assert not st.worker_outputs
    replies = _agent_replies(st, "worker1")
    assert replies
    assert "START" in (replies[-1].get("visible_text") or "") or replies[-1].get("visible_text")


def test_worker_intake_assignment_id_from_dict_open_question():
    pipe = Pipeline(EventBus())
    pipe.flex_desk.open_questions = lambda: [{"assignment_id": "C9", "component": "start_work"}]
    st = pipe.worker_intake("Prüfe nur tests/test_health.py.", worker_id="worker1")
    replies = _agent_replies(st, "worker1")
    assert replies
    assert "START-C9" in (replies[-1].get("visible_text") or "")


def test_flex_send_replies_without_execute():
    pipe = Pipeline(EventBus())
    st = pipe.chat_turn("Nur bestätigen, nichts merken.", target="flex")
    assert not st.worker_outputs
    replies = _agent_replies(st, "flex")
    assert replies


def test_invalid_target_no_silent_brainstorm():
    pipe = Pipeline(EventBus())
    before = pipe.state.send_target
    with pytest.raises(ValueError, match="invalid send target"):
        pipe.chat_turn("x", target="ghost")
    assert pipe.state.send_target == before
    assert not _agent_replies(pipe.state, "brainstorm")


def test_api_invalid_target_is_400(tmp_path, monkeypatch):
    import os

    from gnom_hub import hub as hub_mod

    monkeypatch.delenv("GNOM_WS", raising=False)
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "0")
    for key in list(os.environ):
        if key.endswith("_API_KEY") or key in ("DEEPSEEK_API_KEY", "WORKER_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    client = TestClient(create_app())
    res = client.post("/api/chat?sync=true", json={"text": "hi", "target": "ghost"})
    assert res.status_code == 400
    assert "ghost" in res.text or "target" in res.text.lower()
    hub_mod._HUB = None


def test_js_chat_uses_send_target_not_clicked_card():
    js = Path("src/gnom_hub/ui/static/parts/03-chat-jobs-ops.js").read_text(encoding="utf-8")
    assert "function appendChat(who, text, agentId)" in js or "appendChat(who, text, conv" in js
    assert "syncActiveChatLog(lastClickedAgentId" not in js.split("function appendChat")[1][:500]
    assert "Send+Exec" not in js
    assert "sendTarget" in js


def test_allowed_targets_frozen():
    assert "brainstorm" in ALLOWED_SEND_TARGETS
    assert "ghost" not in ALLOWED_SEND_TARGETS


def test_empty_user_text_fails_without_recording():
    pipe = Pipeline(EventBus())
    st = pipe.chat_turn("   ", target="brainstorm")
    assert st.error == "Empty user text"
    assert st.stage == PipelineStage.error
    assert not st.messages
    assert not st.worker_outputs


def test_tool_drill_early_return_records_without_execute():
    pipe = Pipeline(EventBus(), tools=object())
    st = pipe.chat_turn("Tool drill S6 plugins", target="brainstorm")
    assert st.stage != PipelineStage.done
    assert not st.worker_outputs
    assert st.mode != "execute"
    users = [
        m
        for m in (st.messages or [])
        if m.get("role") == "user" and m.get("target_agent_id") == "brainstorm"
    ]
    assert users
    replies = _agent_replies(st, "brainstorm")
    assert replies
    assert "keine Arbeit" in (replies[-1].get("visible_text") or "")
    assert replies[-1].get("in_reply_to") == users[-1]["message_id"]


def test_live_browser_early_return_records_without_execute():
    pipe = Pipeline(EventBus(), tools=object())
    st = pipe.chat_turn("öffne https://example.com", target="brainstorm")
    assert st.stage != PipelineStage.done
    assert not st.worker_outputs
    replies = _agent_replies(st, "brainstorm")
    assert replies
    assert "Live-Browser" in (replies[-1].get("visible_text") or "")


def test_api_async_invalid_target_is_400(tmp_path, monkeypatch):
    import os

    from gnom_hub import hub as hub_mod

    monkeypatch.delenv("GNOM_WS", raising=False)
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "0")
    for key in list(os.environ):
        if key.endswith("_API_KEY") or key in ("DEEPSEEK_API_KEY", "WORKER_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    client = TestClient(create_app())
    res = client.post("/api/chat", json={"text": "hi", "target": "ghost"})
    assert res.status_code == 400
    assert "ghost" in res.text or "target" in res.text.lower()
    hub_mod._HUB = None


def test_worker_assignment_id_from_dict_or_object():
    from gnom_hub.flex_desk import FlexQuestion
    from gnom_hub.pipeline.orchestrator import _question_assignment_id

    q = FlexQuestion(
        question_id="q1",
        job_id="j1",
        task_id="plan",
        agent_id="flex",
        component="start_work",
        text="START-C1",
        assignment_id="C1",
    )
    assert _question_assignment_id(q) == "C1"
    assert _question_assignment_id({"assignment_id": "C2"}) == "C2"
    assert _question_assignment_id({}) == ""
