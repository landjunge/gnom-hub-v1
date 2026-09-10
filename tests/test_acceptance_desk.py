"""Desk acceptance paths that do not need a live LLM key."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app
from gnom_hub.hub import Hub
from gnom_hub.tools.tool_scenarios import run_forced_tool_scenario


def _isolate(tmp_path, monkeypatch) -> None:
    # Do not patch config.paths.project_root: tmp would count as the real hub and leak GNOM_WS keys.
    monkeypatch.delenv("GNOM_WS", raising=False)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None


def test_ui_hosts_include_dod_checklist():
    html = Path("src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
    assert 'id="flex-ask"' in html
    assert 'id="box3-dod-checklist"' in html
    assert 'id="tools-dod-fail"' in html
    assert 'id="box3-tool-strip"' in html


def test_send_toast_does_not_claim_build_auto_executes():
    """Send = talk; Arbeit starten / Ja in Box 1 = work."""
    part = Path("src/gnom_hub/ui/static/parts/03-chat-jobs-ops.js").read_text(encoding="utf-8")
    app = Path("src/gnom_hub/ui/static/app.js").read_text(encoding="utf-8")
    stale = "harter Bau-Befehl = sofort"
    assert stale not in part
    assert stale not in app
    assert "Pipeline von selbst" not in part
    assert "Pipeline von selbst" not in app
    toast = "Send = sprechen · Arbeit starten / Ja in Box 1 = Arbeit"
    assert toast in part
    assert toast in app


def test_flex_answer_start_work_polls_job_like_execute():
    """start_work POST returns a job envelope; UI must poll, not wipe Box 1."""
    part = Path("src/gnom_hub/ui/static/parts/01-api-snapshot-tts.js").read_text(encoding="utf-8")
    app = Path("src/gnom_hub/ui/static/app.js").read_text(encoding="utf-8")
    for src in (part, app):
        body = src.split("async function answerFlexQuestion", 1)[1].split(
            "function renderFlexBox1", 1
        )[0]
        assert "pollJob(start.job_id" in body
        assert "wants_start_work" in body
        assert "applySnapshot(start)" not in body
        assert body.index("pollJob") < body.index("applySnapshot(snap)")
        apply = src.split("function applySnapshot(snap)", 1)[1][:900]
        assert "snap.job_id && !snap.pipeline && !snap.flex_box1" in apply
        assert "flexShowsCoordinator" in src


def test_tts_one_voice_per_agent():
    part = Path("src/gnom_hub/ui/static/parts/01-api-snapshot-tts.js").read_text(encoding="utf-8")
    app = Path("src/gnom_hub/ui/static/app.js").read_text(encoding="utf-8")
    for src in (part, app):
        assert "function pickVoiceForAgent" in src
        assert "function pitchForAgent" in src
        assert 'ttsQueue.push({ text: p, agentId: String(agentId || "") })' in src
        assert 'speakOrQueue(label + ". " + body, agentId)' in src
        assert 'speakOrQueue(spoken, "flex")' in src


def test_chat_copy_and_remember_buttons():
    part = Path("src/gnom_hub/ui/static/parts/03-chat-jobs-ops.js").read_text(encoding="utf-8")
    app = Path("src/gnom_hub/ui/static/app.js").read_text(encoding="utf-8")
    css = Path("src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")
    for src in (part, app):
        assert 'className = "chat-act-copy"' in src
        assert 'className = "chat-act-keep"' in src
        assert '"/api/memory/warm"' in src
        assert "navigator.clipboard.writeText" in src
    assert "overflow-y: scroll" in css
    assert "#box2 .agent-layer-body" in css
    assert ".flex-ask-card" in css
    flex = Path("src/gnom_hub/ui/static/parts/01-api-snapshot-tts.js").read_text(encoding="utf-8")
    assert "Mehrfachauswahl — antippen, dann Senden" in flex
    assert "Mehrfachauswahl — antippen, dann Senden" in app


def test_flex_box1_text_multi_select_later_are_answerable():
    """text/free_text: field+submit; multi_select: pick then send; later without options."""
    part = Path("src/gnom_hub/ui/static/parts/01-api-snapshot-tts.js").read_text(encoding="utf-8")
    app = Path("src/gnom_hub/ui/static/app.js").read_text(encoding="utf-8")
    for src in (part, app):
        body = src.split("function renderFlexBox1", 1)[1].split("function applySnapshot", 1)[0]
        assert 'comp === "free_text" || comp === "text"' in body
        assert 'className = "flex-ask-free"' in body
        assert 'inp.type = "text"' in body
        assert 'comp === "multi_select"' in body
        assert "picked.slice()" in body
        assert "picked.indexOf" in body
        assert 'comp === "later"' in body
        assert '"Später"' in body
        assert "addLaterIfMissing" in body


def test_tool_drill_s6_plugins_forced(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    h = Hub()
    try:
        r = run_forced_tool_scenario(h.tools, "Tool drill S6 plugins", bus=h.bus)
        assert r.get("ok") is True
        assert int(r.get("tool_calls") or 0) >= 1
        summary = str(r.get("summary") or "")
        assert "S6" in summary or "file_list" in summary or "plugin" in summary.lower()
    finally:
        hub_mod._HUB = None


def test_html_execute_one_worker_and_validation_without_key(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    h = Hub()
    try:
        h.pipeline.brainstorm_turn("Baue eine komplette Landingpage HTML mit dark theme und Hero")
        st = h.pipeline.execute()
        if st.stage.value == "clarify":
            st = h.pipeline.answer_clarify("Schnell und einfach")
        assert st.stage.value == "done"
        assert st.resolved_plan_mode == "full_page_html"
        assert len(st.worker_outputs or []) == 1
        gate = (st.worker_outputs or [{}])[0].get("validation") or {}
        assert isinstance(gate, dict)
        assert gate.get("checklist")
        # Honest fail — no fake success HTML (missing key → worker_error; stub HTML → incomplete)
        assert gate.get("ok") is False
        assert gate.get("issues")
    finally:
        hub_mod._HUB = None


def test_api_tool_drill_and_busy_409(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/chat?sync=1", json={"text": "Tool drill S6 plugins"})
        assert r.status_code == 200
        p = r.json().get("pipeline") or {}
        assert p.get("stage") == "done"
        assert (
            len(p.get("tool_log") or []) >= 1 or "tool" in str(p.get("quality_notes") or "").lower()
        )

        # async job → second chat should 409 while busy (or finish instantly)
        j = c.post("/api/chat", json={"text": "Landingpage Gnom-Hub v1 mit Effects jetzt bauen"})
        # may be 200 if finished super fast; only assert 409 when busy
        if j.status_code == 200:
            busy = c.get("/api/jobs/busy")
            if busy.status_code == 200 and (busy.json() or {}).get("busy"):
                r2 = c.post("/api/chat", json={"text": "x"})
                assert r2.status_code == 409
        c.post("/api/jobs/cancel-busy")
    hub_mod._HUB = None
