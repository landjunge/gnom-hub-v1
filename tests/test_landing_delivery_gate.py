"""Merge-gate: HTML is GELIEFERT only when the page is complete and loads."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from gnom_hub.pipeline.dod_gate import html_complete, interaction_required, run_dod_check
from gnom_hub.pipeline.html_browser_check import (
    PAGE_INCOMPLETE_MSG,
    attach_browser_checks,
    verify_worker_html,
)
from gnom_hub.snapshot_ops import _deliverable_ok

_REPO = Path(__file__).resolve().parents[1]
BOXES_JS = (_REPO / "src/gnom_hub/ui/static/parts/09-boxes.js").read_text(encoding="utf-8")

COMPLETE_LANDING = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Bean &amp; Bloom</title></head>
<body>
  <header><h1>Bean &amp; Bloom</h1></header>
  <main>
    <p>Coffee shop landing with hours, beans, and a short story.</p>
    <button id="cta" type="button" onclick="this.textContent='Thanks'">Order</button>
  </main>
  <footer>Contact · Berlin</footer>
</body>
</html>
"""

LONG_FRAGMENT = (
    "<section class='hero'>" + ("Landing copy for the coffee shop. " * 24) + "</section>"
)


def _st(body: str, *, user_text: str, validation=None, extra=None):
    out = {"worker": "worker1", "result": body, "task": "landing HTML"}
    if validation is not None:
        out["validation"] = validation
    if extra:
        out.update(extra)
    return SimpleNamespace(
        user_text=user_text,
        worker_outputs=[out],
        worker_results=[body],
        result_status="",
        quality_notes="",
        stage="done",
    )


def test_long_html_fragment_is_not_deliverable():
    assert len(LONG_FRAGMENT) >= 400
    assert not html_complete(LONG_FRAGMENT)
    st = _st(LONG_FRAGMENT, user_text="Build a landing page HTML for Bean & Bloom")
    assert _deliverable_ok(st) is False


def test_complete_landing_is_deliverable_without_browser():
    gate = run_dod_check(
        COMPLETE_LANDING,
        user_text="Build a landing page HTML with a click demo",
        task="landing HTML click demo",
    )
    st = _st(
        COMPLETE_LANDING,
        user_text="Build a landing page HTML with a click demo",
        validation=gate,
    )
    assert gate.get("html_complete") is True
    assert _deliverable_ok(st) is True


def test_finish_fragment_is_nachbesserung_not_ungeprueft():
    from gnom_hub.hub import Hub
    from gnom_hub.pipeline.models import PipelineStage

    h = Hub()
    st = h.pipeline.state
    st.user_text = "Build a landing page HTML for Bean & Bloom coffee"
    st.worker_outputs = [
        {"worker": "worker1", "result": LONG_FRAGMENT, "validation": {"ok": False}}
    ]
    st.worker_results = [LONG_FRAGMENT]
    h.pipeline._finish()
    assert st.stage == PipelineStage.done
    assert st.result_status == "NACHBESSERUNG"
    assert st.result_status != "UNGEPRÜFT"
    assert PAGE_INCOMPLETE_MSG in (st.quality_notes or "")
    snap = h.snapshot()
    assert snap["pipeline"]["deliverable_ok"] is False
    rev = snap.get("flex_review") or {}
    assert PAGE_INCOMPLETE_MSG in (rev.get("question") or "")
    assert "good" not in [b.get("id") for b in (rev.get("buttons") or [])]


def test_finish_complete_html_geliefert_when_browser_ok(monkeypatch):
    from gnom_hub.hub import Hub

    monkeypatch.setattr(
        "gnom_hub.pipeline.html_browser_check.verify_worker_html",
        lambda *a, **k: {
            "ok": True,
            "skipped": False,
            "issues": [],
            "pageerrors": [],
            "screenshot": True,
            "structure": True,
        },
    )
    gate = run_dod_check(
        COMPLETE_LANDING,
        user_text="Build a landing page HTML with a click demo",
        task="landing HTML click demo",
    )
    h = Hub()
    st = h.pipeline.state
    st.user_text = "Build a landing page HTML with a click demo"
    st.worker_outputs = [
        {"worker": "worker1", "result": COMPLETE_LANDING, "task": "click demo", "validation": gate}
    ]
    st.worker_results = [COMPLETE_LANDING]
    h.pipeline._finish()
    assert _deliverable_ok(st) is True
    assert st.result_status == "GELIEFERT"


def test_verify_skips_without_playwright(monkeypatch):
    monkeypatch.setattr("gnom_hub.pipeline.html_browser_check.playwright_available", lambda: False)
    r = verify_worker_html(COMPLETE_LANDING, interaction_required=True)
    assert r.get("skipped") is True
    assert r.get("ok") is False


def test_attach_marks_incomplete_without_launching(monkeypatch):
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("must not launch")

    monkeypatch.setattr("gnom_hub.pipeline.html_browser_check.verify_worker_html", boom)
    st = _st(LONG_FRAGMENT, user_text="Build a landing page HTML")
    attach_browser_checks(st)
    assert called["n"] == 0
    bc = st.worker_outputs[0]["browser_check"]
    assert bc.get("ok") is False
    assert "incomplete_html" in (bc.get("issues") or [])


def test_box3_preview_and_fullscreen_share_sandbox():
    assert "const WORKER_IFRAME_SANDBOX" in BOXES_JS
    assert "allow-scripts" in BOXES_JS
    sandboxes = re.findall(r'setAttribute\(\s*"sandbox",\s*([^)]+)\)', BOXES_JS)
    assert sandboxes
    assert all("WORKER_IFRAME_SANDBOX" in s for s in sandboxes)
    assert (
        re.search(r'setAttribute\(\s*"sandbox",\s*"allow-same-origin allow-forms', BOXES_JS) is None
    )
    fs_idx = BOXES_JS.find("function openWorkerFullscreen")
    assert fs_idx != -1
    assert "WORKER_IFRAME_SANDBOX" in BOXES_JS[fs_idx : fs_idx + 2500]


def test_interaction_required_from_task_language():
    assert interaction_required("landing html", "page with click demo") is True
    assert interaction_required("plain landing html page", "static page") is False


def test_playwright_loads_complete_landing():
    pytest.importorskip("playwright")
    r = verify_worker_html(COMPLETE_LANDING, interaction_required=True)
    if r.get("skipped"):
        pytest.skip(str(r.get("reason") or "playwright skipped"))
    assert r.get("ok") is True
    assert not r.get("pageerrors")
    assert r.get("screenshot") is True
    assert r.get("structure") is True


def test_playwright_rejects_broken_script():
    pytest.importorskip("playwright")
    broken = (
        "<!DOCTYPE html><html><head><title>x</title></head><body>"
        "<h1>Hi</h1><script>throw new Error('boom-gate')</script>"
        "<button onclick='1'>go</button></body></html>"
    )
    r = verify_worker_html(broken, interaction_required=False)
    if r.get("skipped"):
        pytest.skip(str(r.get("reason") or "playwright skipped"))
    assert r.get("ok") is False
    assert "pageerror" in (r.get("issues") or [])
