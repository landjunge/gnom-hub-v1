"""Agent detail page: tabs, recipient, live status, no dumped API keys."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
PREAMBLE = (ROOT / "src/gnom_hub/ui/static/parts/00-preamble.js").read_text(encoding="utf-8")

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

LIVE_STATUS_LABELS = (
    "wartet",
    "denkt",
    "fragt nach",
    "benutzt Werkzeug",
    "hat Ergebnis",
    "blockiert",
    "Fehler",
)

_ASSIGN_SEND_TARGET = re.compile(r"\bsendTarget\s*=(?!=)")


def _function_body(src: str, name: str) -> str:
    needle = f"function {name}"
    if needle not in src:
        raise AssertionError(f"missing {needle}")
    start = src.index(needle)
    brace = src.index("{", start)
    depth = 0
    for i, ch in enumerate(src[brace:], brace):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[brace : i + 1]
    raise AssertionError(f"unclosed function {name}")


def test_html_lang_de():
    assert 'lang="de"' in HTML


def test_html_agent_page_tabs_and_set_target():
    assert 'id="agent-page-tabs"' in HTML
    assert 'id="agent-page-set-target"' in HTML
    assert "Als Empfänger wählen" in HTML
    assert "agent-page-tab" in HTML
    assert "agent-page-panel" in HTML
    for tab in AGENT_PAGE_TABS:
        assert f'data-tab="{tab}"' in HTML
        assert f'id="agent-page-panel-{tab}"' in HTML


def test_html_agent_page_tab_buttons():
    for tab in AGENT_PAGE_TABS:
        class_then_tab = rf'<button\b[^>]*class="[^"]*agent-page-tab[^"]*"[^>]*data-tab="{tab}"'
        tab_then_class = rf'<button\b[^>]*data-tab="{tab}"[^>]*class="[^"]*agent-page-tab[^"]*"'
        assert re.search(class_then_tab, HTML) or re.search(tab_then_class, HTML), (
            f"missing agent-page-tab button data-tab={tab}"
        )


def test_html_agent_page_not_paragraph_only():
    """Tabs/panels replace a 35-paragraph-only agent page."""
    assert "agent-page-panel" in HTML
    assert "agent-page-tab" in HTML


def test_preamble_open_agent_page_exists():
    assert "function openAgentPage" in PREAMBLE


def test_preamble_open_agent_page_does_not_assign_send_target():
    body = _function_body(PREAMBLE, "openAgentPage")
    assert _ASSIGN_SEND_TARGET.search(body) is None


def test_preamble_set_target_assigns_send_target():
    assert "function bindAgentPage" in PREAMBLE
    body = _function_body(PREAMBLE, "bindAgentPage")
    assert "agent-page-set-target" in body
    assert "Als Empfänger" in HTML or "Als Empfänger" in body
    assert _ASSIGN_SEND_TARGET.search(body) is not None


def test_preamble_never_dumps_api_key():
    assert "API-Schlüssel werden nicht angezeigt" in PREAMBLE
    assert "agent.api_key" not in PREAMBLE


def test_preamble_agent_live_status():
    has_fn = "agentLiveStatus" in PREAMBLE
    has_labels = all(label in PREAMBLE for label in LIVE_STATUS_LABELS)
    assert has_fn or has_labels


def test_preamble_bind_agent_page():
    assert "function bindAgentPage" in PREAMBLE
