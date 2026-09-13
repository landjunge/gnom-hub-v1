"""R4.10: Header, toasts, usage modal, stage badge in German."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
CHAT_JS = (ROOT / "src/gnom_hub/ui/static/parts/03-chat-jobs-ops.js").read_text(encoding="utf-8")
SNAP_JS = (ROOT / "src/gnom_hub/ui/static/parts/01-api-snapshot-tts.js").read_text(encoding="utf-8")
USAGE_JS = (ROOT / "src/gnom_hub/ui/static/parts/02-modals-tools-ws.js").read_text(encoding="utf-8")


def test_toolbar_buttons_are_german():
    bar = HTML.split('class="top-toolbar"', 1)[1].split("agent-cards", 1)[0]
    assert "Chat leeren" in bar
    assert "Archiv" in bar
    assert "Speichern" in bar
    assert "Clear chat" not in bar
    assert ">Save<" not in bar
    assert "Reset" not in bar
    assert "Archive HOT" not in bar


def test_stage_badge_maps_idle_to_leer():
    assert 'idle: "leer"' in SNAP_JS
    assert 'execute: "Arbeit"' in SNAP_JS
    assert ">leer<" in HTML.split('id="stage-badge"', 1)[1][:80]


def test_header_toasts_german():
    assert "Chat geleert" in CHAT_JS
    assert "Gespeichert" in CHAT_JS
    assert "Sitzung neu" in CHAT_JS
    assert "Nach COLD archiviert" in CHAT_JS
    assert "Arbeit läuft" in CHAT_JS
    assert "Chat log cleared" not in CHAT_JS
    assert "Saved HOT memory" not in CHAT_JS


def test_usage_modal_german():
    chunk = HTML.split('id="usage-modal"', 1)[1].split("help-modal", 1)[0]
    assert "Kosten und Jobs" in chunk
    assert "Aktualisieren" in chunk
    assert "Zähler leeren" in chunk
    assert "Usage & Jobs" not in chunk
    assert "Ausgegeben:" in USAGE_JS
    assert "spent: $" not in USAGE_JS
    assert "Werkzeuge: 0" in SNAP_JS
