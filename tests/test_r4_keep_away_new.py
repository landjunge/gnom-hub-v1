"""R4.4: Weg, Neu, Behalten — honest persist, restore, variant tab."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")
BOXES_JS = (ROOT / "src/gnom_hub/ui/static/parts/09-boxes.js").read_text(encoding="utf-8")
PREAMBLE_JS = (ROOT / "src/gnom_hub/ui/static/parts/00-core.js").read_text(encoding="utf-8")


def _box3() -> str:
    return HTML.split('id="box3"', 1)[1].split('id="tune-layer"', 1)[0]


def test_keep_away_new_restore_are_in_keep_bar():
    chunk = _box3()
    assert 'class="box3-keep-bar"' in chunk
    bar = chunk.split('class="box3-keep-bar"', 1)[1].split("box3-tool-strip", 1)[0]
    assert ">Weg<" in bar
    assert ">Neu<" in bar
    assert ">Behalten<" in bar
    assert ">Zurück<" in bar
    assert 'id="box3-btn-restore"' in bar
    actions = chunk.split("box3-result-actions", 1)[1].split("box3-keep-bar", 1)[0]
    assert ">Weg<" not in actions
    assert ">Behalten<" not in actions


def test_keep_success_requires_verified():
    assert "data.verified !== true" in BOXES_JS
    assert "Speichern nicht bestätigt" in BOXES_JS
    assert "Behalten — im Workspace gespeichert" in BOXES_JS


def test_away_toasts_only_after_write():
    assert "Weg — im Papierkorb" in BOXES_JS
    assert "Papierkorb nicht geschrieben" in BOXES_JS
    assert "Weg — im Papierkorb, wiederherstellbar" not in BOXES_JS


def test_restore_puts_last_away_back():
    assert "box3-btn-restore" in BOXES_JS
    assert "resultTrash.shift" in BOXES_JS
    assert "Zurück — wieder in Box 3" in BOXES_JS


def test_neu_keeps_original_and_marks_variant():
    assert "variant_of" in BOXES_JS
    assert 'return base + "v"' in BOXES_JS
    assert "Original bleibt" in BOXES_JS
    assert "noch nicht gespeichert" in BOXES_JS


def test_keep_bar_equal_flex_white():
    assert ".box3-keep-bar" in CSS
    block = CSS.split(".box3-keep-bar {", 1)[1].split("}", 1)[0]
    assert "width: 100%" in block
    btn = CSS.split(".box3-keep-bar .btn-ws-sm {", 1)[1].split("}", 1)[0]
    assert "flex: 1 1 0" in btn
    assert "color: #fff" in btn
    assert "height: var(--btn-h)" in btn


def test_agent_page_away_label_is_weg():
    assert 'awayBtn.textContent = "Weg"' in PREAMBLE_JS
    assert 'awayBtn.textContent = "Verwerfen"' not in PREAMBLE_JS
