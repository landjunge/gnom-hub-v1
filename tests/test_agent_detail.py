"""Agent detail page: tabs, recipient, live status, no dumped API keys."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
PREAMBLE = (ROOT / "src/gnom_hub/ui/static/parts/00-preamble.js").read_text(encoding="utf-8")
INIT = (ROOT / "src/gnom_hub/ui/static/parts/05-init.js").read_text(encoding="utf-8")
CSS = (ROOT / "src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")

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


def test_html_agent_page_header_ltr():
    assert 'id="agent-page-back"' in HTML
    assert "Zurück zum Desk" in HTML
    assert 'id="agent-page-swatch"' in HTML
    assert 'id="agent-page-glyph"' in HTML
    assert 'id="agent-page-title"' in HTML
    assert 'id="agent-page-role"' in HTML
    assert 'id="agent-page-live"' in HTML
    assert 'id="agent-page-live-sym"' in HTML
    assert 'id="agent-page-live-text"' in HTML
    assert 'id="agent-page-model"' in HTML
    assert 'id="agent-page-runtime"' in HTML
    assert 'id="agent-page-cost"' in HTML
    assert 'id="agent-page-set-target"' in HTML
    expert_btn = re.search(
        r'<button\b[^>]*id="agent-page-expert"[^>]*>',
        HTML,
    )
    assert expert_btn, "expert control must remain in markup"
    assert "hidden" in expert_btn.group(0)


def test_html_agent_page_uses_cards_not_line_walls():
    assert "agent-page-card" in PREAMBLE
    assert "agent-page-empty" in PREAMBLE
    assert "Keine Daten" in PREAMBLE
    jetzt = _function_body(PREAMBLE, "fillAgentPageJetzt")
    assert "agent-page-card" in jetzt
    assert "agent-page-line" not in jetzt


def test_dateien_zones_german():
    body = _function_body(PREAMBLE, "fillAgentPageDateien")
    assert "Gelesen" in body
    assert "Erzeugt" in body
    assert "Geändert" in body
    assert "Selected" not in body
    assert '"Temp"' not in body
    assert "'Temp'" not in body
    assert '"Perm"' not in body
    assert "'Perm'" not in body


def test_memory_hot_warm_cold_distinct():
    body = _function_body(PREAMBLE, "fillAgentPageMemory")
    assert "edge-hot" in body
    assert "edge-warm" in body
    assert "edge-cold" in body
    assert "HOT" in body
    assert "WARM" in body
    assert "COLD" in body


def test_live_status_maps_pipeline_labels():
    token = _function_body(PREAMBLE, "agentLiveStatusToken")
    assert '"denkt"' in token or "denkt" in token
    assert "aktiv" in token
    assert "fragt nach" in token
    assert "hat Ergebnis" in token
    assert "fertig" in token
    assert "benutzt Werkzeug" in token
    assert "laedt" in token or "lädt" in PREAMBLE
    assert "offline" in token


def test_esc_closes_agent_page():
    assert 'ev.key === "Escape"' in INIT
    assert "closeAgentPage" in INIT


def test_close_agent_page_does_not_assign_send_target():
    body = _function_body(PREAMBLE, "closeAgentPage")
    assert _ASSIGN_SEND_TARGET.search(body) is None


def test_god_mode_status_only_on_agent_page():
    body = _function_body(PREAMBLE, "fillAgentPageEinstellungen")
    assert "God-Mode" in body
    assert "nur Status" in body
    assert "set_god_mode" not in body
    assert "god_mode.enabled" in body or "god_mode" in body


def test_ergebnis_uses_preview_card_not_blob_dump():
    body = _function_body(PREAMBLE, "fillAgentPageErgebnis")
    assert "agent-page-preview" in body
    assert "Ansehen" in body
    assert "slice(0, 597)" not in body


def test_css_agent_page_tokens():
    assert "--bg: #121316" in CSS
    assert "--bg-strip: #15171b" in CSS
    assert "--border-strong: #5c616a" in CSS
    assert "--border-hover: #6b7280" in CSS
    assert "--ok: #3d9b6a" in CSS
    assert "--btn-h: 28px" in CSS
    assert "--tab-h: 32px" in CSS
