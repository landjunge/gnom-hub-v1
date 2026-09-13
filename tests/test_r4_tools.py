"""R4.5: Tools modal — German, Sicht/Code, God only via badge."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
TOOLS_JS = (ROOT / "src/gnom_hub/ui/static/parts/02-modals-tools-ws.js").read_text(encoding="utf-8")
INIT_JS = (ROOT / "src/gnom_hub/ui/static/parts/05-init.js").read_text(encoding="utf-8")


def _tools_html() -> str:
    return HTML.split('id="tools-modal"', 1)[1].split('id="usage-modal"', 1)[0]


def test_toolbar_tools_button_is_werkzeuge():
    m = re.search(r'id="btn-tools"[^>]*>([^<]*)<', HTML)
    assert m, "missing #btn-tools"
    assert m.group(1).strip() == "Werkzeuge"


def test_tools_modal_sicht_code_not_json_first():
    chunk = _tools_html()
    assert ">Sicht<" in chunk
    assert ">Code<" in chunk
    assert "function formatToolCallGerman" in TOOLS_JS
    assert "function setToolsResult" in TOOLS_JS
    assert "JSON.stringify(clean, null, 2)" not in TOOLS_JS
    assert "formatToolCallGerman(c)" in TOOLS_JS


def test_tools_modal_has_no_god_switch():
    chunk = _tools_html()
    assert "god-badge" not in chunk
    assert "God einschalten" not in chunk
    assert 'id="cu-god-toggle"' not in chunk
    assert "god_mode.enabled" not in chunk or "POST" not in chunk
    assert "/api/god" not in TOOLS_JS


def test_computer_use_toasts_are_german():
    assert "Trockenlauf — God-Badge oben für echte Steuerung" in TOOLS_JS
    assert "Dry-run click" not in TOOLS_JS
    assert "Screenshot saved" not in TOOLS_JS
    assert "enable God badge first" not in TOOLS_JS


def test_tools_run_toasts_are_german():
    assert "Werkzeug wählen" in TOOLS_JS
    assert "Select a tool" not in TOOLS_JS
    assert "Holen ok" in TOOLS_JS
    assert "Fetch ok" not in TOOLS_JS
    assert "Verlauf kopiert" in TOOLS_JS
    assert "Tool history copied" not in TOOLS_JS
    assert "Verlauf aktualisiert" in INIT_JS
