"""Flex review rebuild/fix buttons must not start Execute.

Contract: Flex has no execute authority. Gate is #btn-execute or Box 1
start_work Ja. Review actions may offer_start_work and return a snapshot
that wants Box 1 confirmation.
"""

from __future__ import annotations

import pytest

from gnom_hub.config import paths
from gnom_hub.pipeline.models import PipelineStage


def _hub(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.hub import Hub

    monkeypatch.delenv("GNOM_WS", raising=False)
    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    hub = Hub()
    return hub, hub_mod


def _long_html() -> str:
    body = "<p>coffee shop landing with hero footer and cards.</p>" * 20
    return f"<!DOCTYPE html><html><head><title>Bean</title></head><body>{body}</body></html>"


def _arm_done(hub, *, quality_notes: str = "", deliverable: bool = True) -> None:
    st = hub.pipeline.state
    st.stage = PipelineStage.done
    st.brainstorm_notes = "Landing page: dunkles Theme, Hero, Footer, klickbare Buttons."
    st.user_text = "Build a landing page HTML"
    if deliverable:
        html = _long_html()
        st.worker_outputs = [{"worker": "worker1", "name": "Worker 1", "result": html}]
        st.worker_results = [html]
    else:
        body = (
            "Worker 1 FEHLER - kein Deliverable\n"
            "LLM-Fehler (worker1): tollgate package not installed\n"
            "Kein Stub-Ersatz. Key pruefen, Budget pruefen, dann erneut ausfuehren."
        )
        st.worker_outputs = [{"worker": "worker1", "name": "Worker 1", "result": body}]
        st.worker_results = [body]
    st.quality_notes = quality_notes


def _spy_execute(hub) -> list[str]:
    called: list[str] = []
    hub.execute_sync = lambda: called.append("sync") or {"ok": True}  # type: ignore[method-assign]
    hub.execute_async = (  # type: ignore[method-assign]
        lambda: called.append("async") or {"ok": True, "job_id": "should-not-run"}
    )
    hub.execute = lambda: called.append("execute") or {"ok": True}  # type: ignore[method-assign]
    return called


def _start_work_questions(hub, snap: dict | None = None) -> list:
    desk_qs = [q for q in hub.pipeline.flex_desk.open_questions() if q.component == "start_work"]
    box1 = (snap or {}).get("flex_box1") or {}
    snap_qs = [q for q in (box1.get("questions") or []) if q.get("component") == "start_work"]
    return desk_qs, snap_qs


def test_rebuild_does_not_call_execute(tmp_path, monkeypatch):
    hub, hub_mod = _hub(tmp_path, monkeypatch)
    try:
        _arm_done(hub)
        called = _spy_execute(hub)
        out = hub.apply_flex_feedback("rebuild")
        assert called == []
        assert out.get("ok") is True
        assert out.get("action") != "execute"
        job = out.get("job")
        assert not job or not job.get("job_id")
        desk_qs, snap_qs = _start_work_questions(hub, out.get("snapshot"))
        assert desk_qs, "rebuild must offer_start_work on FlexDesk"
        assert snap_qs, "snapshot must show Box 1 start_work confirmation"
        assert "Arbeit jetzt starten" in desk_qs[0].text
        with pytest.raises(PermissionError):
            hub.pipeline.flex_desk.start_execute()
    finally:
        hub_mod._HUB = None


def test_rebuild_without_deliverable_does_not_execute(tmp_path, monkeypatch):
    hub, hub_mod = _hub(tmp_path, monkeypatch)
    try:
        _arm_done(hub, deliverable=False)
        called = _spy_execute(hub)
        out = hub.apply_flex_feedback("rebuild")
        assert called == []
        assert out.get("ok") is True
        desk_qs, snap_qs = _start_work_questions(hub, out.get("snapshot"))
        assert desk_qs
        assert snap_qs
    finally:
        hub_mod._HUB = None


def test_fix_html_does_not_call_execute(tmp_path, monkeypatch):
    hub, hub_mod = _hub(tmp_path, monkeypatch)
    try:
        _arm_done(hub, quality_notes="incomplete HTML document, missing </html>")
        called = _spy_execute(hub)
        panel = hub.flex_review_panel()
        ids = [b.get("id") for b in (panel.get("buttons") or [])]
        assert "fix_html" in ids
        out = hub.apply_flex_feedback("fix_html")
        assert called == []
        assert out.get("ok") is True
        assert out.get("action") != "execute"
        desk_qs, snap_qs = _start_work_questions(hub, out.get("snapshot"))
        assert desk_qs
        assert snap_qs
        with pytest.raises(PermissionError):
            hub.pipeline.flex_desk.start_execute()
    finally:
        hub_mod._HUB = None


def test_add_js_does_not_call_execute(tmp_path, monkeypatch):
    hub, hub_mod = _hub(tmp_path, monkeypatch)
    try:
        _arm_done(hub, quality_notes="no onclick interaction on the page")
        called = _spy_execute(hub)
        panel = hub.flex_review_panel()
        ids = [b.get("id") for b in (panel.get("buttons") or [])]
        assert "add_js" in ids
        out = hub.apply_flex_feedback("add_js")
        assert called == []
        assert out.get("ok") is True
        assert out.get("action") != "execute"
        desk_qs, _snap_qs = _start_work_questions(hub, out.get("snapshot"))
        assert desk_qs
    finally:
        hub_mod._HUB = None


def test_review_rebuild_buttons_are_not_execute_actions(tmp_path, monkeypatch):
    hub, hub_mod = _hub(tmp_path, monkeypatch)
    try:
        _arm_done(
            hub,
            quality_notes="incomplete HTML and missing onclick interaction",
        )
        panel = hub.flex_review_panel()
        assert panel.get("active") is True
        by_id = {b.get("id"): b for b in (panel.get("buttons") or [])}
        for bid in ("rebuild", "fix_html", "add_js"):
            btn = by_id[bid]
            assert btn.get("action") != "execute", bid
            assert btn.get("action") == "start_work", bid
        _arm_done(hub, deliverable=False)
        no_deliv = hub.flex_review_panel()
        rebuild = next(b for b in no_deliv["buttons"] if b.get("id") == "rebuild")
        assert rebuild.get("action") != "execute"
        assert rebuild.get("action") == "start_work"
    finally:
        hub_mod._HUB = None
