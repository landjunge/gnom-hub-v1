"""Quiet Box 3: DoD strip stays hidden on hard fail; banner is German."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOX = (ROOT / "src/gnom_hub/ui/static/parts/09-boxes.js").read_text(encoding="utf-8")
TOOLS = (ROOT / "src/gnom_hub/ui/static/parts/04-tools.js").read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    return src.split("function " + name, 1)[1].split("\n  function ", 1)[0]


def test_dod_strip_hidden_on_hard_fail():
    body = _fn(BOX, "renderDodChecklist")
    assert "hardFail || !soft" in body
    assert 'head.textContent = "Hinweis"' in body
    assert "score " not in body
    assert "retryable" not in body


def test_fehler_banner_german():
    body = _fn(BOX, "showBox3ResultStage")
    assert "FEHLER — Auftrag nicht erfüllt" in body
    assert "DoD fail" not in body
    assert "Auftrag nicht erfüllt" in body


def test_tools_fail_line_german():
    assert "Auftrag nicht erfüllt" in TOOLS
    assert "DoD nicht erfüllt" not in TOOLS
