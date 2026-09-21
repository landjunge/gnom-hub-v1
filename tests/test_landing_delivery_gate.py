"""Merge-gate: HTML is GELIEFERT only when the page is complete and loads."""

from __future__ import annotations

import asyncio
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
APP_JS = (_REPO / "src/gnom_hub/ui/static/app.js").read_text(encoding="utf-8")

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
    assert interaction_required("landing html with information about hours", "static page") is False
    assert interaction_required("landing html", "contact form") is True
    assert interaction_required("Informationen zu Öffnungszeiten", "statische Seite") is False
    assert interaction_required("Landing HTML mit Kontaktformular", "") is True


def test_fragment_does_not_poison_skipped_complete_page(monkeypatch):
    from gnom_hub.hub import Hub

    monkeypatch.setattr(
        "gnom_hub.pipeline.html_browser_check.verify_worker_html",
        lambda *a, **k: {
            "ok": False,
            "skipped": True,
            "reason": "playwright_unavailable",
            "issues": [],
            "pageerrors": [],
            "screenshot": False,
        },
    )
    gate = run_dod_check(
        COMPLETE_LANDING,
        user_text="Build a landing page HTML for Bean & Bloom",
        task="landing HTML",
    )
    h = Hub()
    st = h.pipeline.state
    st.user_text = "Build a landing page HTML for Bean & Bloom"
    st.worker_outputs = [
        {
            "worker": "worker1",
            "result": COMPLETE_LANDING,
            "task": "landing HTML",
            "validation": gate,
        },
        {"worker": "worker2", "result": LONG_FRAGMENT, "validation": {"ok": False}},
    ]
    st.worker_results = [COMPLETE_LANDING, LONG_FRAGMENT]
    h.pipeline._finish()
    assert _deliverable_ok(st) is True
    assert st.result_status == "UNGEPRÜFT"
    assert st.result_status != "NACHBESSERUNG"
    assert PAGE_INCOMPLETE_MSG not in (st.quality_notes or "")


def test_chromium_missing_is_executable_only():
    from gnom_hub.pipeline.html_browser_check import _chromium_executable_missing

    assert _chromium_executable_missing(
        RuntimeError("Executable doesn't exist at /tmp/chromium/chrome")
    )
    assert _chromium_executable_missing(RuntimeError("Executable not found"))
    assert _chromium_executable_missing(RuntimeError("Browser is not installed"))
    assert _chromium_executable_missing(RuntimeError("Browsers are not installed"))
    assert not _chromium_executable_missing(
        RuntimeError("Failed to launch chromium because of sandbox")
    )
    assert not _chromium_executable_missing(RuntimeError("timeout waiting for browser"))


def test_verify_worker_html_from_asyncio_loop():
    from concurrent.futures import ThreadPoolExecutor

    def _with_running_loop():
        async def _go():
            return verify_worker_html(COMPLETE_LANDING)

        return asyncio.run(_go())

    # Fresh thread so pytest-asyncio's loop cannot block asyncio.run.
    with ThreadPoolExecutor(max_workers=1) as pool:
        r = pool.submit(_with_running_loop).result(timeout=60)
    err = str(r.get("error") or "")
    assert "Sync API inside the asyncio loop" not in err
    assert "page_load_error" not in (r.get("issues") or [])


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


def test_verify_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("GNOM_HTML_BROWSER_CHECK", "0")
    monkeypatch.setattr(
        "gnom_hub.pipeline.html_browser_check.playwright_available",
        lambda: True,
    )
    r = verify_worker_html(COMPLETE_LANDING, interaction_required=True)
    assert r.get("skipped") is True
    assert r.get("reason") == "disabled"
    assert r.get("ok") is False


def test_verify_incomplete_html_does_not_launch(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not launch")

    monkeypatch.setattr("gnom_hub.pipeline.html_browser_check.playwright_available", boom)
    r = verify_worker_html(LONG_FRAGMENT)
    assert r.get("ok") is False
    assert r.get("skipped") is False
    assert "incomplete_html" in (r.get("issues") or [])


def test_failed_browser_check_blocks_deliverable_ok():
    gate = run_dod_check(
        COMPLETE_LANDING,
        user_text="Build a landing page HTML",
        task="landing HTML",
    )
    st = _st(
        COMPLETE_LANDING,
        user_text="Build a landing page HTML",
        validation=gate,
        extra={
            "browser_check": {
                "ok": False,
                "skipped": False,
                "issues": ["pageerror"],
            }
        },
    )
    assert _deliverable_ok(st) is False


def test_skipped_browser_check_does_not_block_deliverable_ok():
    gate = run_dod_check(
        COMPLETE_LANDING,
        user_text="Build a landing page HTML",
        task="landing HTML",
    )
    st = _st(
        COMPLETE_LANDING,
        user_text="Build a landing page HTML",
        validation=gate,
        extra={
            "browser_check": {
                "ok": False,
                "skipped": True,
                "reason": "disabled",
                "issues": [],
            }
        },
    )
    assert _deliverable_ok(st) is True


def test_finish_browser_fail_is_nachbesserung_not_geliefert(monkeypatch):
    from gnom_hub.hub import Hub

    monkeypatch.setattr(
        "gnom_hub.pipeline.html_browser_check.verify_worker_html",
        lambda *a, **k: {
            "ok": False,
            "skipped": False,
            "issues": ["pageerror"],
            "pageerrors": ["boom-gate"],
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
        {
            "worker": "worker1",
            "result": COMPLETE_LANDING,
            "task": "click demo",
            "validation": gate,
        }
    ]
    st.worker_results = [COMPLETE_LANDING]
    h.pipeline._finish()
    assert st.result_status == "NACHBESSERUNG"
    assert st.result_status != "GELIEFERT"
    assert st.result_status != "UNGEPRÜFT"
    assert PAGE_INCOMPLETE_MSG in (st.quality_notes or "")
    assert _deliverable_ok(st) is False


def test_failed_complete_page_not_ignored_when_other_skipped(monkeypatch):
    from gnom_hub.hub import Hub

    other = COMPLETE_LANDING.replace("Bean &amp; Bloom", "Other Cafe")

    def fake_verify(html, **k):
        if "Other Cafe" in html:
            return {
                "ok": False,
                "skipped": False,
                "issues": ["pageerror"],
                "pageerrors": ["boom"],
                "screenshot": True,
                "structure": True,
            }
        return {
            "ok": False,
            "skipped": True,
            "reason": "playwright_unavailable",
            "issues": [],
            "pageerrors": [],
            "screenshot": False,
        }

    monkeypatch.setattr(
        "gnom_hub.pipeline.html_browser_check.verify_worker_html",
        fake_verify,
    )
    gate_ok = run_dod_check(
        COMPLETE_LANDING,
        user_text="Build a landing page HTML for Bean & Bloom",
        task="landing HTML",
    )
    gate_other = run_dod_check(
        other,
        user_text="Build a landing page HTML for Bean & Bloom",
        task="landing HTML",
    )
    h = Hub()
    st = h.pipeline.state
    st.user_text = "Build a landing page HTML for Bean & Bloom"
    st.worker_outputs = [
        {
            "worker": "worker1",
            "result": COMPLETE_LANDING,
            "task": "landing HTML",
            "validation": gate_ok,
        },
        {
            "worker": "worker2",
            "result": other,
            "task": "landing HTML",
            "validation": gate_other,
        },
    ]
    st.worker_results = [COMPLETE_LANDING, other]
    h.pipeline._finish()
    assert st.result_status == "NACHBESSERUNG"
    assert st.result_status != "UNGEPRÜFT"
    assert PAGE_INCOMPLETE_MSG in (st.quality_notes or "")


def test_attach_keeps_existing_browser_check(monkeypatch):
    called = {"n": 0}

    def count(*a, **k):
        called["n"] += 1
        return {"ok": True, "skipped": False, "issues": []}

    monkeypatch.setattr("gnom_hub.pipeline.html_browser_check.verify_worker_html", count)
    st = _st(COMPLETE_LANDING, user_text="Build a landing page HTML")
    st.worker_outputs[0]["browser_check"] = {
        "ok": True,
        "skipped": False,
        "issues": [],
        "cached": True,
    }
    attach_browser_checks(st)
    assert called["n"] == 0
    assert st.worker_outputs[0]["browser_check"].get("cached") is True


def test_interact_selectors_prefer_button_before_href():
    from gnom_hub.pipeline.html_browser_check import _INTERACT_SELECTORS

    sels = list(_INTERACT_SELECTORS)
    assert sels.index("button") < sels.index("a[href]")
    assert sels.index("[onclick]") < sels.index("a[href]")


def test_app_js_bundle_shares_sandbox():
    assert "const WORKER_IFRAME_SANDBOX" in APP_JS
    assert "allow-scripts" in APP_JS
    sandboxes = re.findall(r'setAttribute\(\s*"sandbox",\s*([^)]+)\)', APP_JS)
    assert sandboxes
    assert all("WORKER_IFRAME_SANDBOX" in s for s in sandboxes)
    assert (
        re.search(r'setAttribute\(\s*"sandbox",\s*"allow-same-origin allow-forms', APP_JS) is None
    )


def _fake_playwright_raising(exc: Exception):
    def _launch(**_kw):
        raise exc

    class FakeP:
        def __init__(self):
            self.chromium = SimpleNamespace(launch=_launch)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    return lambda: FakeP()


@pytest.mark.parametrize(
    "exc,skipped,reason",
    [
        (
            RuntimeError("Failed to launch chromium because of sandbox"),
            False,
            "launch_error",
        ),
        (
            RuntimeError("Executable doesn't exist at /tmp/chromium/chrome"),
            True,
            "chromium_missing",
        ),
    ],
)
def test_playwright_sync_launch_skip_only_when_binary_missing(monkeypatch, exc, skipped, reason):
    pytest.importorskip("playwright")
    monkeypatch.setattr("playwright.sync_api.sync_playwright", _fake_playwright_raising(exc))
    from gnom_hub.pipeline.html_browser_check import _playwright_sync

    r = _playwright_sync(COMPLETE_LANDING, interaction_required=False, timeout_ms=2000)
    assert r.get("skipped") is skipped
    assert r.get("reason") == reason
    if skipped:
        assert r.get("issues") == []
    else:
        assert "page_load_error" in (r.get("issues") or [])


def test_playwright_clicks_button_not_link():
    pytest.importorskip("playwright")
    html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Click order</title></head>
<body>
  <main>
    <a href="#" onclick="throw new Error('link-clicked')">leave</a>
    <button id="cta" type="button" onclick="this.dataset.ok='1'">stay</button>
  </main>
</body>
</html>
"""
    r = verify_worker_html(html, interaction_required=True)
    if r.get("skipped"):
        pytest.skip(str(r.get("reason") or "playwright skipped"))
    assert "link-clicked" not in " ".join(r.get("pageerrors") or [])
    assert "interaction_failed" not in (r.get("issues") or [])
    assert r.get("ok") is True
