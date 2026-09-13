"""Wave 2 desk: mic latch, agent page, keep verify, DE default."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.export_ops import ExportOpsMixin
from gnom_hub.memory.workspace import WorkspaceStore


def test_html_wave2_surfaces():
    html = Path("src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
    assert 'id="agent-page"' in html
    assert 'id="agent-page-back"' in html
    assert 'id="agent-page-expert"' in html
    assert 'id="box2-reply-tabs"' in html
    assert 'id="box3-btn-away"' in html
    assert 'id="box3-btn-new"' in html
    assert 'id="box3-btn-keep"' in html
    assert ">Behalten<" in html
    assert 'lang="de"' in html
    assert 'id="chat-targets"' in html
    assert 'id="tune-temp-reset"' in html
    assert 'id="tune-topp-reset"' in html
    assert 'id="tune-maxtok-reset"' in html
    assert 'id="tune-freq-reset"' in html
    assert 'id="tune-pres-reset"' in html


def test_mic_stays_on_until_click():
    js = Path("src/gnom_hub/ui/static/parts/08-chat-jobs.js").read_text(encoding="utf-8")
    assert "recognition.continuous = true" in js
    assert "recognition.start()" in js
    assert "Mikrofon aus" in js


def test_keep_does_not_overwrite_silently(tmp_path):
    ws = WorkspaceStore(tmp_path)
    html = "<!DOCTYPE html><html><body>a</body></html>"
    p1 = ws.keep_html_content(html, "page.html")
    assert p1.is_file()
    staged = ws.stage_recovery(html + "x", "page.html")
    assert staged.is_file()
    dest = ws.selected / "page.html"
    assert dest.exists()
    try:
        ws.keep_html_content(html + "z", "page.html")
        raise AssertionError("silent overwrite")
    except FileExistsError:
        pass
    assert dest.read_text(encoding="utf-8") == html
    p2 = ws.keep_html_content(html + "z", "page.html", overwrite=True)
    assert p2.read_text(encoding="utf-8") == html + "z"


def _keep_hub(tmp_path: Path) -> ExportOpsMixin:
    class _State:
        def __init__(self) -> None:
            self.worker_outputs: list = []

    class _Pipe:
        def __init__(self) -> None:
            self.state = _State()

    class Hub(ExportOpsMixin):
        def __init__(self) -> None:
            self.workspace = WorkspaceStore(tmp_path)
            self.pipeline = _Pipe()

        def _append_trace(self, *_a, **_k) -> None:
            return None

    return Hub()


def test_keep_text_result_goes_to_perm_and_verifies(tmp_path):
    hub = _keep_hub(tmp_path)
    out = hub.keep_result_to_personal_ws("plain notes", name="notes.txt")
    assert out["ok"] is True
    assert out["verified"] is True
    dest = Path(out["path"])
    assert dest.parent.name == "perm"
    assert dest.read_text(encoding="utf-8") == "plain notes"
    again = hub.keep_result_to_personal_ws("other", name="notes.txt")
    assert again["ok"] is False
    assert again["error"] == "exists"
    assert dest.read_text(encoding="utf-8") == "plain notes"


def test_keep_html_still_selected(tmp_path):
    hub = _keep_hub(tmp_path)
    html = "<!DOCTYPE html><html><body>kept</body></html>"
    out = hub.keep_result_to_personal_ws(html, name="page.html")
    assert out["ok"] is True
    assert Path(out["path"]).parent.name == "selected"
    assert Path(out["path"]).read_text(encoding="utf-8") == html


def test_agent_page_never_dumps_api_key():
    js = Path("src/gnom_hub/ui/static/parts/00-core.js").read_text(encoding="utf-8")
    assert "function openAgentPage" in js
    assert "API-Schlüssel werden nicht angezeigt" in js
    assert "agent.api_key" not in js
    assert "/api/skills" in js
    assert "agent-page-skill" in js


def test_toast_queue_and_hover_pause():
    js = Path("src/gnom_hub/ui/static/parts/00-core.js").read_text(encoding="utf-8")
    assert "flushToasts" in js
    assert "mouseenter" in js
    assert "TOAST_MAX" in js


def test_keep_ui_accepts_non_html():
    js = Path("src/gnom_hub/ui/static/parts/09-boxes.js").read_text(encoding="utf-8")
    assert "Kein HTML — Behalten gilt nur für HTML" not in js
    assert 'zone: "trash"' in js or "zone: 'trash'" in js
    assert "stageResultsRecovery" in js
