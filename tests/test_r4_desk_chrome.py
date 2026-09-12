"""R4.3 remaining desk chrome — square 20px tokens, German Box 3 / overlays."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")
BOXES_JS = (ROOT / "src/gnom_hub/ui/static/parts/04-boxes.js").read_text(encoding="utf-8")

_RADIUS_ZERO = re.compile(r"border-radius\s*:\s*0(px)?\b")
_OPEN_ID = re.compile(
    r"""<([a-zA-Z][\w:-]*)\b([^>]*\bid=["']([^"']+)["'][^>]*)>""",
    re.DOTALL,
)


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


def _inner_by_id(html: str, eid: str) -> str:
    m = None
    for cand in _OPEN_ID.finditer(html):
        if cand.group(3) == eid:
            m = cand
            break
    if m is None:
        raise AssertionError(f"missing id={eid!r}")
    tag = m.group(1)
    start = m.end()
    if m.group(0).rstrip().endswith("/>"):
        return ""
    depth = 1
    i = start
    open_pat = re.compile(rf"<{re.escape(tag)}\b[^>]*>", re.IGNORECASE)
    close_pat = re.compile(rf"</{re.escape(tag)}\s*>", re.IGNORECASE)
    while i < len(html) and depth:
        om = open_pat.search(html, i)
        cm = close_pat.search(html, i)
        if cm is None:
            raise AssertionError(f"unclosed {tag}#{eid}")
        if om is not None and om.start() < cm.start():
            void = html[om.start() : om.end()].rstrip().endswith("/>")
            if not void:
                depth += 1
            i = om.end()
        else:
            depth -= 1
            if depth == 0:
                return html[start : cm.start()]
            i = cm.end()
    raise AssertionError(f"unclosed {tag}#{eid}")


def _visible_text(inner: str) -> str:
    text = re.sub(r"<!--.*?-->", "", inner, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def test_btn_h_tab_h_are_20px():
    assert "--btn-h: 20px" in CSS
    assert "--tab-h: 20px" in CSS
    assert "--border-strong: #5c616a" in CSS


def test_box3_worker_tab_square_20px():
    bodies = _css_rules_for(".box3-worker-tab")
    assert bodies, "missing .box3-worker-tab"
    joined = "\n".join(bodies)
    assert _RADIUS_ZERO.search(joined), ".box3-worker-tab must be square"
    assert re.search(r"height\s*:\s*(20px|var\(--tab-h\))", joined), (
        ".box3-worker-tab height must be 20px or var(--tab-h)"
    )


def test_top_toolbar_button_radius_zero():
    bodies = _css_rules_for(".top-toolbar button")
    if not bodies:
        bodies = _css_rules_for("button")
    joined = "\n".join(_css_rules_for(".btn-workspace") + _css_rules_for(".btn-save"))
    assert _RADIUS_ZERO.search(joined) or "border-radius: 0" in CSS, (
        "toolbar buttons must set border-radius: 0"
    )
    assert re.search(
        r"\.top-toolbar button[\s\S]{0,400}border-radius:\s*0",
        CSS,
    )


def test_toast_and_badges_radius_zero():
    toast = "\n".join(_css_rules_for(".toast"))
    assert toast, "missing .toast"
    assert _RADIUS_ZERO.search(toast), ".toast must be square"
    badge = "\n".join(_css_rules_for(".god-badge"))
    assert _RADIUS_ZERO.search(badge), ".god-badge must be square (red on-state unchanged)"


def test_box3_keep_away_new_are_german():
    assert ">Behalten<" in HTML
    assert ">Weg<" in HTML
    assert ">Neu<" in HTML
    assert ">Kopieren<" in HTML
    assert ">Copy<" not in _inner_by_id(HTML, "box3")
    assert ">Keep<" not in _inner_by_id(HTML, "box3")
    assert ">Delete<" not in _inner_by_id(HTML, "box3")
    assert ">Preview<" not in _inner_by_id(HTML, "box3")


def test_box3_preview_source_js_are_vorschau_quelle():
    assert 'name + " Preview"' not in BOXES_JS
    assert "HTML-Preview" not in BOXES_JS
    assert "HTML-Vorschau" in BOXES_JS
    assert "Vorschau" in BOXES_JS
    assert "Quelltext" in BOXES_JS


def test_all_scrollbars_hidden_globally_still_overflow():
    """Desk: no visible bars; overflow auto/scroll still there."""
    assert re.search(r"\*\s*\{[^}]*scrollbar-width:\s*none", CSS, re.DOTALL)
    assert "*::-webkit-scrollbar" in CSS
    webkit = CSS.split("*::-webkit-scrollbar", 1)[1][:160]
    assert "width: 0" in webkit
    assert "overflow-y: auto" in CSS or "overflow: auto" in CSS
    assert "function hideScrollbarCss" in BOXES_JS
    assert "function withHiddenScrollbars" in BOXES_JS
    assert "scrollbar-width:none" in BOXES_JS
    assert "::-webkit-scrollbar" in BOXES_JS


def test_box2_dyn_content_can_scroll():
    """Box 2 text/HTML must overflow-y auto, not clip with overflow hidden."""
    stage = "\n".join(_css_rules_for(".dyn-stage"))
    assert "overflow-y: auto" in stage, ".dyn-stage must scroll"
    assert not re.search(r"overflow\s*:\s*hidden", stage), (
        ".dyn-stage must not clip with overflow: hidden"
    )
    src = "\n".join(_css_rules_for(".dyn-source"))
    assert "overflow-y: auto" in src, ".dyn-source must scroll"
    assert "#box2 .dyn-stage" in CSS
    box2_src = CSS.split("#box2 .dyn-stage", 1)[1][:400]
    assert "overflow-y: auto" in box2_src


def test_overlay_titles_german_chrome():
    ws = _visible_text(_inner_by_id(HTML, "workspace-modal"))
    assert "Vorschau" in ws
    assert "Temp leeren" in ws
    assert "Dauerhaft" in ws
    sys_txt = _visible_text(_inner_by_id(HTML, "system-modal"))
    assert "Übernehmen" in sys_txt
    assert "Löschen" in sys_txt
    tools = _visible_text(_inner_by_id(HTML, "tools-modal"))
    assert "Werkzeuge" in tools
    assert "Ausführen" in tools
    assert re.search(r'id="btn-help"[^>]*>\s*Hilfe\s*<', HTML), (
        "#btn-help visible label must be Hilfe"
    )
