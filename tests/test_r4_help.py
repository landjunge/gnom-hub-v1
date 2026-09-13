"""R4.9: navigable Help modal, not a Box 1 text wall."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
CHAT_JS = (ROOT / "src/gnom_hub/ui/static/parts/08-chat-jobs.js").read_text(encoding="utf-8")
OPS = (ROOT / "src/gnom_hub/system_ops.py").read_text(encoding="utf-8")
CSS = (ROOT / "src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")


def test_help_modal_exists_with_tabs():
    assert 'id="help-modal"' in HTML
    assert 'id="help-tabs"' in HTML
    assert 'id="help-body"' in HTML
    assert 'id="help-close"' in HTML


def test_help_opens_modal_not_box1_wall():
    body = CHAT_JS.split("async function onHelp", 1)[1].split(
        "async function restoreBackupByName", 1
    )[0]
    assert "help-modal" in body or "helpModal" in body
    assert "tipRoot.hidden = false" not in body
    assert "paintHelpTopic" in body
    assert "HELP_TOPICS" in CHAT_JS


def test_help_topics_are_german_and_short():
    assert '"Senden"' in OPS or '"senden"' in OPS
    assert "God geht nur über den roten Badge" in OPS
    assert "Telegram: /hot" not in OPS
    assert "Cost badge + Compact" not in OPS
    assert '"points"' in OPS
    assert "help-list" in CHAT_JS
    assert "help-nicht" in CHAT_JS
    assert "pick.body" in CHAT_JS


def test_help_tabs_equal_flex_white():
    tab = CSS.split(".help-tab {", 1)[1].split("}", 1)[0]
    assert "flex: 1 1 0" in tab
    assert "color: #fff" in tab
    assert "height: var(--tab-h)" in tab
