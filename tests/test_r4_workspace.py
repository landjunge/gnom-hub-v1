"""R4.6: Workspace modal — Temp, Dauerhaft, Behalten; German; HTML Sicht."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.memory.workspace import WorkspaceStore

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
WS_JS = (ROOT / "src/gnom_hub/ui/static/parts/02-modals-tools-ws.js").read_text(encoding="utf-8")


def _modal() -> str:
    return HTML.split('id="workspace-modal"', 1)[1].split('id="system-modal"', 1)[0]


def test_workspace_has_three_columns_including_selected():
    chunk = _modal()
    assert 'id="ws-temp-list"' in chunk
    assert 'id="ws-perm-list"' in chunk
    assert 'id="ws-selected-list"' in chunk
    assert ">Behalten<" in chunk
    assert 'id="ws-preview-sicht"' in chunk
    assert 'id="ws-preview-code"' in chunk
    assert 'id="ws-preview-frame"' in chunk


def test_workspace_toasts_are_german():
    assert "Workspace load failed" not in WS_JS
    assert 'toast("Promoted "' not in WS_JS and "toast('Promoted '" not in WS_JS
    assert "Temp cleared" not in WS_JS
    assert 'toast("Gelöscht: "' in WS_JS or "toast('Gelöscht: '" in WS_JS
    assert "Nach Dauerhaft übernommen" in WS_JS
    assert "Gelöscht: " in WS_JS
    assert "Temp geleert" in WS_JS
    assert "Zip bereit" in WS_JS
    assert "Datei löschen:" in WS_JS


def test_workspace_lists_selected_from_snapshot():
    assert "snap.selected" in WS_JS
    assert "ws-selected-list" in WS_JS
    assert "leer — Behalten in Box 3" in WS_JS


def test_selected_zone_read_write(tmp_path):
    ws = WorkspaceStore(tmp_path)
    html = "<!DOCTYPE html><html><body>behalten</body></html>"
    path = ws.keep_html_content(html, "page.html")
    assert path.parent.name == "selected"
    listed = ws.list_selected()
    assert any(f["name"] == "page.html" for f in listed)
    text = ws.read_text("selected", "page.html")
    assert "behalten" in text
    snap = ws.snapshot()
    assert any(f["name"] == "page.html" for f in snap["selected"])
    zpath = ws.export_zip("selected")
    assert zpath.is_file()
    assert "selected" in zpath.name
