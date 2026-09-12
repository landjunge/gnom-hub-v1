"""R4.2: Box 2 reply tabs — German labels, square tabs (source asserts)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")
BOXES_JS = (ROOT / "src/gnom_hub/ui/static/parts/04-boxes.js").read_text(encoding="utf-8")
SNAP_JS = (ROOT / "src/gnom_hub/ui/static/parts/01-api-snapshot-tts.js").read_text(encoding="utf-8")
CHAT_JS = (ROOT / "src/gnom_hub/ui/static/parts/03-chat-jobs-ops.js").read_text(encoding="utf-8")

_RADIUS_ZERO = re.compile(r"border-radius\s*:\s*0(px)?\b")
_RADIUS_FOUR = re.compile(r"border-radius\s*:\s*4px\b")
_FONT_SIZE = re.compile(r"font-size\s*:\s*([^;]+)")
_ALLOWED_PX = frozenset({"10px", "12px", "14px", "16px"})
_FONT_VAR = re.compile(r"^var\(--(?:t-[a-z0-9-]+|tab-h)\)$")
_TC_PREVIEW = re.compile(r"""\.textContent\s*=\s*["']Preview["']""")
_TC_SOURCE = re.compile(r"""\.textContent\s*=\s*["']Source["']""")
_TC_VORSCHAU = re.compile(r"""\.textContent\s*=\s*["']Vorschau["']""")
_TC_QUELLE = re.compile(r"""\.textContent\s*=\s*["']Quelle["']""")
_TURN_LIT = re.compile(r"""["']turn["']""")
_SEND_TARGET_ASSIGN = re.compile(r"\bsendTarget\s*=")


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
    """Declaration bodies of base rules whose selector list includes `selector`."""
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


def _idle_set_box2() -> str:
    idx = SNAP_JS.find('p.stage === "idle"')
    if idx < 0:
        idx = SNAP_JS.find("p.stage === 'idle'")
    if idx < 0:
        raise AssertionError("missing idle Box 2 empty copy in 01-api-snapshot-tts.js")
    return SNAP_JS[idx : idx + 600]


def test_box2_reply_tab_border_radius_zero_not_4px():
    """`.box2-reply-tab` is square: border-radius 0, not 4px."""
    bodies = _css_rules_for(".box2-reply-tab")
    assert bodies, "missing .box2-reply-tab in app.css"
    joined = "\n".join(bodies)
    assert _RADIUS_ZERO.search(joined), (
        ".box2-reply-tab must set border-radius: 0 (not 4px); got " + joined.strip()
    )
    assert _RADIUS_FOUR.search(joined) is None, ".box2-reply-tab still has border-radius: 4px"


def test_box2_reply_tab_font_size_token_or_even_px_not_11():
    """font-size 10/12/14/16px or var(--t-* / --tab-h), not 11px."""
    bodies = _css_rules_for(".box2-reply-tab")
    assert bodies, "missing .box2-reply-tab in app.css"
    joined = "\n".join(bodies)
    sizes = [m.group(1).strip() for m in _FONT_SIZE.finditer(joined)]
    assert sizes, ".box2-reply-tab has no font-size"
    for val in sizes:
        assert val != "11px", ".box2-reply-tab font-size is 11px (want 10/12/14/16 or var)"
        ok = val in _ALLOWED_PX or _FONT_VAR.fullmatch(val) is not None
        assert ok, (
            f".box2-reply-tab font-size {val!r} must be 10px/12px/14px/16px "
            "or var(--t-*) / var(--tab-h)"
        )


def test_render_dynamic_content_preview_source_are_vorschau_quelle():
    """Visible Preview/Source strings become Vorschau and Quelle."""
    body = _function_body(BOXES_JS, "renderDynamicContent")
    assert _TC_PREVIEW.search(body) is None, (
        'renderDynamicContent still sets textContent = "Preview"'
    )
    assert _TC_SOURCE.search(body) is None, 'renderDynamicContent still sets textContent = "Source"'
    assert _TC_VORSCHAU.search(body), 'renderDynamicContent must set textContent = "Vorschau"'
    assert _TC_QUELLE.search(body), 'renderDynamicContent must set textContent = "Quelle"'


def test_box2_reply_tabs_label_not_english_turn():
    """renderBox2ReplyTabs does not use English 'turn' as a tab label."""
    body = _function_body(BOXES_JS, "renderBox2ReplyTabs")
    assert _TURN_LIT.search(body) is None, (
        'renderBox2ReplyTabs still uses English "turn" as tab label'
    )


def test_box2_reply_tabs_click_does_not_assign_send_target():
    """Clicking a reply tab must not assign sendTarget."""
    body = _function_body(BOXES_JS, "renderBox2ReplyTabs")
    assert _SEND_TARGET_ASSIGN.search(body) is None, (
        "renderBox2ReplyTabs click handler must not assign sendTarget"
    )


def test_box2_empty_german_contains_antwort_or_reden():
    empty = _idle_set_box2()
    assert "Antwort" in empty or "reden" in empty, (
        f"Box 2 idle empty copy must contain 'Antwort' or 'reden'; got {empty!r}"
    )


def test_send_chat_does_not_start_workers():
    """Communication: sendChat talks only — no execute / start-job."""
    body = _function_body(CHAT_JS, "sendChat")
    assert "/api/chat" in body
    assert "/api/execute" not in body
    assert "/api/reexecute" not in body
    assert "runExecute(" not in body
    assert re.search(r"\bstartJob\s*\(", body) is None
