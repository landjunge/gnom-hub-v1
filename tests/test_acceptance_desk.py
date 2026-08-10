"""Desk acceptance paths that do not need a live LLM key."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from gnom_hub.api.app import create_app
from gnom_hub.hub import Hub
from gnom_hub.tools.tool_scenarios import run_forced_tool_scenario


def test_ui_hosts_include_dod_checklist():
    html = Path("src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
    assert 'id="box3-dod-checklist"' in html
    assert 'id="tools-dod-fail"' in html
    assert 'id="box3-tool-strip"' in html


def test_tool_drill_s6_plugins_forced():
    h = Hub()
    r = run_forced_tool_scenario(h.tools, "Tool drill S6 plugins", bus=h.bus)
    assert r.get("ok") is True
    assert int(r.get("tool_calls") or 0) >= 1
    summary = str(r.get("summary") or "")
    assert "S6" in summary or "file_list" in summary or "plugin" in summary.lower()


def test_html_execute_one_worker_and_validation_without_key():
    h = Hub()
    h.pipeline.brainstorm_turn(
        "Baue eine komplette Landingpage HTML mit dark theme und Hero"
    )
    st = h.pipeline.execute()
    assert st.stage.value == "done"
    assert st.resolved_plan_mode == "full_page_html"
    assert len(st.worker_outputs or []) == 1
    gate = (st.worker_outputs or [{}])[0].get("validation") or {}
    assert isinstance(gate, dict)
    assert gate.get("checklist")
    # No real key → honest FEHLER / DoD fail (not fake success HTML)
    assert gate.get("ok") is False
    assert "worker_error" in (gate.get("issues") or [])


def test_api_tool_drill_and_busy_409():
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/chat?sync=1", json={"text": "Tool drill S6 plugins"})
        assert r.status_code == 200
        p = r.json().get("pipeline") or {}
        assert p.get("stage") == "done"
        assert len(p.get("tool_log") or []) >= 1 or "tool" in str(p.get("quality_notes") or "").lower()

        # async job → second chat should 409 while busy (or finish instantly)
        j = c.post("/api/chat", json={"text": "Landingpage Gnom-Hub v1 mit Effects jetzt bauen"})
        # may be 200 if finished super fast; only assert 409 when busy
        if j.status_code == 200:
            busy = c.get("/api/jobs/busy")
            if busy.status_code == 200 and (busy.json() or {}).get("busy"):
                r2 = c.post("/api/chat", json={"text": "x"})
                assert r2.status_code == 409
        c.post("/api/jobs/cancel-busy")
