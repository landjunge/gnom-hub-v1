"""Quiet desk Q3–Q7: cards, two actions, Box 3, name/tokens, thin toolbar."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
TOKENS = (ROOT / "src/gnom_hub/ui/static/tokens.css").read_text(encoding="utf-8")
CARDS_JS = (ROOT / "src/gnom_hub/ui/static/parts/00-core.js").read_text(encoding="utf-8")
CHAT_JS = (ROOT / "src/gnom_hub/ui/static/parts/08-chat-jobs.js").read_text(encoding="utf-8")
BOX_JS = (ROOT / "src/gnom_hub/ui/static/parts/09-boxes.js").read_text(encoding="utf-8")
SNAP_JS = (ROOT / "src/gnom_hub/ui/static/parts/01-core-api.js").read_text(encoding="utf-8")


def test_q3_cards_are_name_and_status():
    body = CARDS_JS.split("function renderCards", 1)[1].split(
        "function paintChatPlaceholder", 1
    )[0]
    assert "card-name" in body
    assert "card-status" in body
    assert "tok:" not in body
    assert "offline" not in body.lower()
    assert "preset:" not in body
    assert "is-target" in body
    assert "Empfänger" in body


def test_q4_execute_needs_key_and_short_placeholder():
    assert 'id="execute-hint"' in HTML
    assert "Nachricht an" in HTML or "Nachricht an" in SNAP_JS or "Nachricht an" in CARDS_JS
    assert "has-key" in SNAP_JS
    assert "Key fehlt" in CHAT_JS or "Key fehlt" in SNAP_JS
    assert "Brainstorm first, then Execute" not in CHAT_JS


def test_q5_box3_keeps_delivery_and_collapses_same_error():
    assert "box3KeepLast" in BOX_JS
    assert "collapseSharedErrors" in BOX_JS
    assert "Kein Deliverable" in BOX_JS or "llm/key" in BOX_JS


def test_q6_name_german_no_tailwind_cdn_square():
    assert "cdn.tailwindcss.com" not in HTML
    assert "Gnom-Hub-V1" in HTML
    assert "Gnom-Hub — Überblick" not in HTML
    assert "--radius-sm: 0" in TOKENS
    assert "--radius-md: 0" in TOKENS
    assert "--radius-lg: 0" in TOKENS
    assert "Du" in CHAT_JS
    assert 'label.textContent = who' not in CHAT_JS or "WHO_DE" in CHAT_JS


def test_q7_toolbar_is_workspace_system_help():
    bar = HTML.split('class="top-toolbar"', 1)[1].split("</div>", 1)[0]
    assert 'id="btn-workspace"' in bar
    assert 'id="btn-system"' in bar
    assert 'id="btn-help"' in bar
    for noisy in (
        "btn-tools",
        "btn-clear-chat",
        "btn-archive",
        "btn-reset",
        "btn-save",
        "flex-preset-select",
    ):
        assert noisy not in bar
    system = HTML.split('id="system-modal"', 1)[1]
    assert 'id="btn-save"' in system
    assert 'id="btn-archive"' in system
    assert 'id="btn-tools"' in system
