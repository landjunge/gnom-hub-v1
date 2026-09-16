"""Box 3 tool strip: only real tool log, German chips, no notes dump."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOX = (ROOT / "src/gnom_hub/ui/static/parts/09-boxes.js").read_text(encoding="utf-8")
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
CORE = (ROOT / "src/gnom_hub/ui/static/parts/01-core-api.js").read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    return src.split("function " + name, 1)[1].split("\n  function ", 1)[0]


def test_strip_ignores_quality_notes():
    body = _fn(BOX, "renderToolStrip")
    assert "qualityNotes" not in body
    assert "/tool/i" not in body
    assert "JSON.stringify" not in body
    assert "Trockenlauf" in body
    assert "Grund: " in body
    assert "Why:" not in body


def test_callers_pass_only_tool_log():
    assert "renderToolStrip(pipeline.tool_log || [])" in BOX
    assert "renderToolStrip(p.tool_log || [])" in CORE
    assert (
        "quality_notes"
        not in BOX.split("function renderBox3Workers", 1)[1].split("function ", 1)[0]
    )


def test_aria_boxen_not_english_panels():
    assert 'aria-label="Boxen"' in HTML
    assert "Main panels" not in HTML
    assert 'aria-label="Boxes"' not in HTML
