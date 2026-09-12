"""Wave 2 desk: mic latch, agent page, keep verify, DE default."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.memory.workspace import WorkspaceStore


def test_html_wave2_surfaces():
    html = Path("src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
    assert 'id="agent-page"' in html
    assert 'id="agent-page-back"' in html
    assert 'id="box2-reply-tabs"' in html
    assert 'id="box3-btn-away"' in html
    assert 'id="box3-btn-new"' in html
    assert 'id="box3-btn-keep"' in html
    assert ">Behalten<" in html
    assert 'lang="de"' in html
    assert 'id="chat-targets"' in html


def test_mic_stays_on_until_click():
    js = Path("src/gnom_hub/ui/static/parts/03-chat-jobs-ops.js").read_text(encoding="utf-8")
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


def test_agent_page_never_dumps_api_key():
    js = Path("src/gnom_hub/ui/static/parts/00-preamble.js").read_text(encoding="utf-8")
    assert "function openAgentPage" in js
    assert "API-Schlüssel werden nicht angezeigt" in js
    assert "agent.api_key" not in js
