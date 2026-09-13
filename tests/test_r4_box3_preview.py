"""R4.3: Box 3 worker tabs and preview — short white labels, Sicht/Code."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")
BOXES_JS = (ROOT / "src/gnom_hub/ui/static/parts/09-boxes.js").read_text(encoding="utf-8")

_SEND_TARGET_ASSIGN = re.compile(r"\bsendTarget\s*=")
_LAST_CLICKED_ASSIGN = re.compile(r"\blastClickedAgentId\s*=")


def _brace_block(src: str, brace: int) -> str:
    if brace < 0 or brace >= len(src) or src[brace] != "{":
        raise AssertionError("expected '{'")
    depth = 0
    for i, ch in enumerate(src[brace:], brace):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[brace : i + 1]
    raise AssertionError("unclosed block")


def _function_body(src: str, name: str) -> str:
    for prefix in (f"async function {name}", f"function {name}"):
        idx = src.find(prefix)
        if idx >= 0:
            brace = src.index("{", idx)
            return _brace_block(src, brace)
    raise AssertionError(f"missing function {name}")


def _css_rules_for(selector: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS):
        sel = m.group(1).strip()
        if sel.startswith(("@", "/*")):
            continue
        for part in sel.split(","):
            part = part.strip()
            if ":" in part:
                continue
            tokens = re.split(r"\s+", part.replace(">", " "))
            if tokens and tokens[-1] == selector:
                out.append(m.group(2))
                break
    return out


def test_box3_empty_german():
    assert "Noch kein Ergebnis" in HTML
    assert "Arbeit starten" in HTML.split('id="box3-empty"', 1)[1][:240]


def test_box3_tabs_short_a_labels():
    body = _function_body(BOXES_JS, "box3WorkerTabLabel")
    assert '"A"' in body and ("return base" in body or 'return "A"' in body)
    render = _function_body(BOXES_JS, "renderBox3WorkerTabs")
    assert "box3WorkerTabLabel" in render
    assert "sendTarget" not in render


def test_box3_tab_click_does_not_assign_send_target():
    body = _function_body(BOXES_JS, "renderBox3WorkerTabs")
    assert _SEND_TARGET_ASSIGN.search(body) is None
    assert _LAST_CLICKED_ASSIGN.search(body) is None
    focus = _function_body(BOXES_JS, "focusBox3WorkerResult")
    assert _SEND_TARGET_ASSIGN.search(focus) is None


def test_box3_tabs_equal_flex_white():
    row = "\n".join(_css_rules_for(".box3-worker-tabs"))
    assert "width: 100%" in row
    tab = "\n".join(_css_rules_for(".box3-worker-tab"))
    assert "flex: 1 1 0" in tab
    assert "color: #fff" in tab


def test_box3_html_preview_is_sicht_code():
    body = _function_body(BOXES_JS, "showBox3ResultStage")
    assert 'textContent = "Sicht"' in body
    assert 'textContent = "Code"' in body
    assert "Quelltext (Worker-Ausgabe)" not in body
    assert 'textContent = "Preview"' not in body
    assert 'textContent = "Source"' not in body


def test_box3_keep_away_new_still_present():
    chunk = HTML.split('id="box3"', 1)[1].split('id="tune-layer"', 1)[0]
    assert ">Behalten<" in chunk
    assert ">Weg<" in chunk
    assert ">Neu<" in chunk
