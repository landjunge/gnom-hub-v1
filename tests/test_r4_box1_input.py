"""R4.1: Box 1 + chat input — German labels, square controls (source asserts)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "src/gnom_hub/ui/static/tokens.css").read_text(encoding="utf-8") + (
    ROOT / "src/gnom_hub/ui/static/app.css"
).read_text(encoding="utf-8")
CHAT_JS = (ROOT / "src/gnom_hub/ui/static/parts/08-chat-jobs.js").read_text(encoding="utf-8")

_OPEN_ID = re.compile(
    r"""<([a-zA-Z][\w:-]*)\b([^>]*\bid=["']([^"']+)["'][^>]*)>""",
    re.DOTALL,
)
_RADIUS_ZERO = re.compile(r"border-radius\s*:\s*0(px)?\b")
_TOKEN_STRONG = re.compile(r"--border-strong\s*:\s*#5c616a\b", re.IGNORECASE)
_SEND_WORD = re.compile(r"\bSend\b")
_SQUARE_SELS = ("#chat-input", ".chat-input", ".chat-input-row", ".btn-send")


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


def _open_tag(html: str, eid: str) -> str:
    for m in _OPEN_ID.finditer(html):
        if m.group(3) == eid:
            return m.group(0)
    raise AssertionError(f"missing id={eid!r}")


def _attr(open_tag: str, name: str) -> str:
    m = re.search(rf"""\b{re.escape(name)}=["']([^"']*)["']""", open_tag)
    return m.group(1) if m else ""


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


def _button_visible(eid: str) -> str:
    return _visible_text(_inner_by_id(HTML, eid))


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


def test_btn_send_visible_text_is_senden():
    """#btn-send body is Senden — title may still mention Send."""
    text = _button_visible("btn-send")
    assert text == "Senden", f"#btn-send visible text {text!r} (want Senden)"
    assert _SEND_WORD.search(text) is None


def test_btn_mic_label_mikrofon():
    open_tag = _open_tag(HTML, "btn-mic")
    text = _button_visible("btn-mic")
    aria = _attr(open_tag, "aria-label")
    assert "Mikrofon" in text or "Mikrofon" in aria, (
        f"#btn-mic label {text!r} aria-label={aria!r} (want Mikrofon)"
    )


def test_btn_cancel_abbrechen():
    text = _button_visible("btn-cancel")
    assert text == "Abbrechen", f"#btn-cancel visible text {text!r} (want Abbrechen)"


def test_btn_execute_arbeit_starten():
    text = _button_visible("btn-execute")
    assert text == "Arbeit starten", f"#btn-execute visible text {text!r} (want Arbeit starten)"


def test_chat_input_placeholder_reden_or_senden():
    open_tag = _open_tag(HTML, "chat-input")
    ph = _attr(open_tag, "placeholder")
    low = ph.lower()
    assert "reden" in low or "Senden" in ph, (
        f"#chat-input placeholder {ph!r} must contain 'reden' or 'Senden'"
    )


def test_box1_empty_placeholder_german_not_agent_klick_only():
    live = _inner_by_id(HTML, "box1-layer-live")
    m = re.search(r'<p\s+class="box1-placeholder"[^>]*>(.*?)</p>', live, re.DOTALL)
    assert m, "missing .box1-placeholder in #box1-layer-live"
    ph = _visible_text(m.group(1))
    assert ph, "Box 1 empty placeholder is blank"
    assert "Agent-Klick → Info hier" not in ph, (
        "Box 1 empty copy must not be only 'Agent-Klick → Info hier'"
    )
    low = ph.lower()
    assert "entscheiden" in low or "flex fragt" in low, (
        f"Box 1 empty copy {ph!r} should mention entscheiden or Flex fragt"
    )


def test_clarify_buttons_include_ja_and_nein():
    inner = _inner_by_id(HTML, "clarify")
    labels = [
        _visible_text(body)
        for body in re.findall(r"<button\b[^>]*>(.*?)</button>", inner, re.DOTALL)
    ]
    assert "Ja" in labels, f"clarify visible labels {labels!r} missing Ja"
    assert "Nein" in labels, f"clarify visible labels {labels!r} missing Nein"


def test_chat_input_square_radius_or_no_rounded_md():
    """Square controls: CSS border-radius 0, or #chat-input without rounded-md."""
    open_tag = _open_tag(HTML, "chat-input")
    classes = _attr(open_tag, "class").split()
    no_rounded = "rounded-md" not in classes
    radius_zero = False
    for sel in _SQUARE_SELS:
        for body in _css_rules_for(sel):
            if _RADIUS_ZERO.search(body):
                radius_zero = True
                break
        if radius_zero:
            break
    assert no_rounded or radius_zero, (
        "#chat-input still has rounded-md and app.css does not set "
        "border-radius: 0 on #chat-input / .chat-input / .chat-input-row / .btn-send"
    )


def test_send_chat_does_not_start_workers():
    """Regression: sendChat talks only — no execute / start-job."""
    body = _function_body(CHAT_JS, "sendChat")
    assert "/api/chat" in body
    assert "/api/execute" not in body
    assert "/api/reexecute" not in body
    assert "runExecute(" not in body
    assert re.search(r"\bstartJob\s*\(", body) is None


def test_border_strong_token_still_in_app_css():
    """R3 prototype token kept for R4 desk chrome."""
    assert _TOKEN_STRONG.search(CSS), "--border-strong: #5c616a missing in tokens.css"
