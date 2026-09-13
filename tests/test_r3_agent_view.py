"""R3 agent detail contract: cards, tokens, no sendTarget on open."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "src/gnom_hub/ui/static/tokens.css").read_text(encoding="utf-8") + (
    ROOT / "src/gnom_hub/ui/static/app.css"
).read_text(encoding="utf-8")
PREAMBLE = (ROOT / "src/gnom_hub/ui/static/parts/00-core.js").read_text(encoding="utf-8")
INIT = (ROOT / "src/gnom_hub/ui/static/parts/10-core-init.js").read_text(encoding="utf-8")
PROTO = ROOT / "src/gnom_hub/ui/static/experiments/agent-detail-r2.html"

AGENT_PAGE_TABS = (
    "jetzt",
    "auftrag",
    "verlauf",
    "werkzeuge",
    "dateien",
    "memory",
    "ergebnis",
    "einstellungen",
)

CANONICAL_LIVE = (
    "lädt",
    "wartet",
    "aktiv",
    "fragt",
    "blockiert",
    "fertig",
    "offline",
)

FILL_FNS = (
    "fillAgentPageJetzt",
    "fillAgentPageAuftrag",
    "fillAgentPageVerlauf",
    "fillAgentPageWerkzeuge",
    "fillAgentPageDateien",
    "fillAgentPageMemory",
    "fillAgentPageErgebnis",
    "fillAgentPageEinstellungen",
)

_ASSIGN_SEND_TARGET = re.compile(r"\bsendTarget\s*=(?!=)")
_PANEL_LINE = re.compile(
    r'_agentPageAdd\(\s*panel\s*,\s*["\']p["\']\s*,\s*["\']agent-page-line["\']',
    re.DOTALL,
)
_CARD_MARK = re.compile(
    r"agent-card-block|agent-kv|"
    r'["\']article["\']|'
    r'["\'][^"\']*\bcard\b[^"\']*["\']',
)
_CSS_RULE = re.compile(r"(?<![\w-])\.agent-page(?![\w-])\s*\{")
_TOKEN_STRONG = re.compile(r"--border-strong\s*:\s*#5c616a\b", re.IGNORECASE)
_RADIUS_ZERO = re.compile(r"border-radius\s*:\s*0(px)?\b")
_GERMAN_ZONES = ("Gelesen", "Erzeugt", "Geändert", "Temporär", "Dauerhaft", "Auswahl")
_ENGLISH_ZONES = ("Selected", "Temp", "Perm")


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
    needle = f"function {name}"
    if needle not in src:
        raise AssertionError(f"missing {needle}")
    start = src.index(needle)
    brace = src.index("{", start)
    return _brace_block(src, brace)


def _css_block(src: str, selector: str = ".agent-page") -> str:
    if selector != ".agent-page":
        pat = re.compile(rf"(?<![\w-]){re.escape(selector)}(?![\w-])\s*\{{")
    else:
        pat = _CSS_RULE
    m = pat.search(src)
    if not m:
        raise AssertionError(f"missing CSS rule {selector}")
    brace = src.index("{", m.start())
    return _brace_block(src, brace)


def _has_card_markup(body: str) -> bool:
    return _CARD_MARK.search(body) is not None


def _panel_line_count(body: str) -> int:
    return len(_PANEL_LINE.findall(body))


def _escape_handlers(*sources: str) -> list[str]:
    out: list[str] = []
    for src in sources:
        for m in re.finditer(r"""ev\.key\s*===\s*["']Escape["']""", src):
            try:
                brace = src.index("{", m.end())
            except ValueError:
                continue
            if brace - m.end() > 80:
                continue
            out.append(_brace_block(src, brace))
    return out


def _live_status_src() -> str:
    parts = [_function_body(PREAMBLE, "agentLiveStatus")]
    if "function agentLiveStatusToken" in PREAMBLE:
        parts.append(_function_body(PREAMBLE, "agentLiveStatusToken"))
    for name in ("AGENT_LIVE_STATUS", "LIVE_STATUS_ALIASES", "agentLiveAliases"):
        idx = PREAMBLE.find(name)
        if idx < 0:
            continue
        brace = PREAMBLE.find("{", idx)
        if 0 <= brace - idx < 80:
            parts.append(_brace_block(PREAMBLE, brace))
    return "\n".join(parts)


def _status_covered(src: str, name: str) -> bool:
    quoted = re.search(rf"""["']{re.escape(name)}["']""", src)
    if quoted:
        return True
    # documented alias table key: lädt: "…" or "lädt":
    key = re.search(rf"""(?:["']{re.escape(name)}["']|{re.escape(name)})\s*:""", src)
    return key is not None


def test_agent_page_css_border_strong_or_radius_zero():
    """R3 chrome: --border-strong #5c616a or square .agent-page."""
    token_ok = _TOKEN_STRONG.search(CSS) is not None
    page_block = _css_block(CSS)
    radius_ok = _RADIUS_ZERO.search(page_block) is not None
    assert token_ok or radius_ok, (
        ".agent-page must use --border-strong: #5c616a or border-radius: 0"
    )


def test_html_eight_agent_page_tabs():
    assert 'id="agent-page-tabs"' in HTML
    for tab in AGENT_PAGE_TABS:
        assert f'data-tab="{tab}"' in HTML
        assert f'id="agent-page-panel-{tab}"' in HTML
    assert len(AGENT_PAGE_TABS) == 8


def test_open_agent_page_does_not_assign_send_target():
    body = _function_body(PREAMBLE, "openAgentPage")
    assert _ASSIGN_SEND_TARGET.search(body) is None


def test_bind_agent_page_set_target_assigns_send_target():
    assert "function bindAgentPage" in PREAMBLE
    body = _function_body(PREAMBLE, "bindAgentPage")
    assert "agent-page-set-target" in body
    assert _ASSIGN_SEND_TARGET.search(body) is not None


def test_fill_jetzt_auftrag_use_cards_not_line_walls():
    """Jetzt/Auftrag must be cards/kv, not a p.agent-page-line dump."""
    jetzt = _function_body(PREAMBLE, "fillAgentPageJetzt")
    auftrag = _function_body(PREAMBLE, "fillAgentPageAuftrag")
    assert _has_card_markup(jetzt), "fillAgentPageJetzt must create card/article markup"
    assert _has_card_markup(auftrag), "fillAgentPageAuftrag must create card/article markup"
    assert _panel_line_count(jetzt) <= 1, (
        "fillAgentPageJetzt still dumps p.agent-page-line on the panel"
    )
    assert _panel_line_count(auftrag) <= 1, (
        "fillAgentPageAuftrag still dumps p.agent-page-line on the panel"
    )


def test_dateien_labels_german_zones():
    body = _function_body(PREAMBLE, "fillAgentPageDateien")
    has_german = any(z in body for z in _GERMAN_ZONES)
    english_only = all(z in body for z in _ENGLISH_ZONES) and not has_german
    assert has_german, "Dateien labels must include Gelesen or German zone names"
    assert not english_only


def test_agent_page_fills_cannot_toggle_god_mode():
    chunks = [_function_body(PREAMBLE, name) for name in FILL_FNS]
    chunks.append(_function_body(PREAMBLE, "bindAgentPage"))
    blob = "\n".join(chunks)
    assert "/api/god-mode" not in blob


def test_close_agent_page_exists():
    assert "function closeAgentPage" in PREAMBLE
    body = _function_body(PREAMBLE, "closeAgentPage")
    assert "agent-page" in body


def test_escape_handler_calls_close_agent_page():
    handlers = _escape_handlers(INIT, PREAMBLE)
    assert handlers, "Esc handler missing in 10-core-init.js or 00-core.js"
    assert any("closeAgentPage" in h for h in handlers), "Esc handler must call closeAgentPage"


def test_live_status_canonical_names():
    src = _live_status_src()
    missing = [name for name in CANONICAL_LIVE if not _status_covered(src, name)]
    assert not missing, (
        "live status mapping missing "
        + ", ".join(missing)
        + " (canonical lädt|wartet|aktiv|fragt|blockiert|fertig|offline "
        + "or documented aliases)"
    )


def test_agent_detail_r2_prototype_exists():
    assert PROTO.is_file(), "experiments/agent-detail-r2.html must not be deleted"
    text = PROTO.read_text(encoding="utf-8")
    assert "Jetzt" in text and "Auftrag" in text
    assert "--border-strong: #5c616a" in text
