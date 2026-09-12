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
_TURN_LIT = re.compile(r"""["']turn["']""")
_SEND_TARGET_ASSIGN = re.compile(r"\bsendTarget\s*=")
_LAST_CLICKED_ASSIGN = re.compile(r"\blastClickedAgentId\s*=")
_ACTIVATE_LAYER = re.compile(r"\bactivateAgentLayer\s*\(")


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


def test_render_dynamic_content_preview_source_are_sicht_code():
    """Visible Preview/Source strings become short Sicht / Code."""
    body = _function_body(BOXES_JS, "renderDynamicContent")
    assert _TC_PREVIEW.search(body) is None, (
        'renderDynamicContent still sets textContent = "Preview"'
    )
    assert _TC_SOURCE.search(body) is None, 'renderDynamicContent still sets textContent = "Source"'
    assert 'textContent = "Sicht"' in body or "textContent = 'Sicht'" in body, (
        'renderDynamicContent must set textContent = "Sicht"'
    )
    assert 'textContent = "Code"' in body or "textContent = 'Code'" in body, (
        'renderDynamicContent must set textContent = "Code"'
    )


def test_box2_reply_tab_height_matches_buttons():
    """Reply tabs share --tab-h with all desk buttons (20px)."""
    bodies = _css_rules_for(".box2-reply-tab")
    assert bodies, "missing .box2-reply-tab in app.css"
    joined = "\n".join(bodies)
    assert re.search(r"height\s*:\s*(20px|var\(--tab-h\))", joined), (
        ".box2-reply-tab must set height: 20px or var(--tab-h); got " + joined.strip()
    )
    css = CSS
    assert "--btn-h: 20px" in css and "--tab-h: 20px" in css


def test_box2_reply_tab_active_uses_agent_color_not_brainstorm_outline():
    """Active tab: agent color bottom edge, not a generic brainstorm outline."""
    bodies = _css_rules_for(".box2-reply-tab.is-on")
    assert bodies, "missing .box2-reply-tab.is-on in app.css"
    joined = "\n".join(bodies)
    assert "--owner-color" in joined, (
        ".box2-reply-tab.is-on must use --owner-color for the active edge"
    )
    assert "var(--c-brainstorm" not in joined, (
        ".box2-reply-tab.is-on still uses a generic brainstorm outline/color"
    )


def test_box2_reply_tabs_label_not_english_turn():
    """renderBox2ReplyTabs does not use English 'turn' as a tab label."""
    body = _function_body(BOXES_JS, "renderBox2ReplyTabs")
    assert _TURN_LIT.search(body) is None, (
        'renderBox2ReplyTabs still uses English "turn" as tab label'
    )
    assert "Coord" in BOXES_JS or '"A"' in BOXES_JS or "Brain" in BOXES_JS, (
        "Box 2 reply tabs must use short agent labels"
    )


def test_box2_reply_tabs_equal_flex_centered_white():
    """Box 2 tabs fill the row equally, sit centered, names are white."""
    row = "\n".join(_css_rules_for(".box2-reply-tabs"))
    assert "justify-content: center" in row, ".box2-reply-tabs must center the row"
    assert "width: 100%" in row, ".box2-reply-tabs must span the box"
    tab = "\n".join(_css_rules_for(".box2-reply-tab"))
    assert "flex: 1 1 0" in tab, ".box2-reply-tab must share equal flex width"
    assert "color: #fff" in tab, ".box2-reply-tab names must be white"
    body = _function_body(BOXES_JS, "box2AgentTabLabel")
    assert 'return "Brain"' in body
    assert 'return "Coord"' in body
    assert 'return "Mem"' in body


def test_box2_reply_tabs_click_does_not_assign_send_target():
    """Clicking a reply tab must not assign sendTarget or lastClicked routing."""
    body = _function_body(BOXES_JS, "renderBox2ReplyTabs")
    assert _SEND_TARGET_ASSIGN.search(body) is None, (
        "renderBox2ReplyTabs click handler must not assign sendTarget"
    )
    assert _LAST_CLICKED_ASSIGN.search(body) is None, (
        "renderBox2ReplyTabs click handler must not assign lastClickedAgentId"
    )
    assert _ACTIVATE_LAYER.search(body) is None, (
        "renderBox2ReplyTabs must not call activateAgentLayer"
    )


def test_close_box2_page_does_not_clear_chat():
    """Page × returns to the answer; chat is not wiped."""
    body = _function_body(BOXES_JS, "closeBox2Page")
    assert "chatLog" not in body
    assert "chat-layers" not in body
    assert "box2-page-stage" in body


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
