"""R4: German desk copy — Send is talk, not Execute."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.ui.tooltips import TOOLTIPS


def test_chat_tooltip_de_send_is_talk():
    de = TOOLTIPS["chat"]["de"]["how_to"]
    assert "reden" in de.lower()
    assert "Arbeit starten" in de
    assert "Brainstorm-Turn" not in de
    assert "Worker-Pipeline" not in de


def test_box2_empty_state_is_german():
    js = Path("src/gnom_hub/ui/static/parts/01-api-snapshot-tts.js").read_text(encoding="utf-8")
    assert "Brainstorm dialogue appears here" not in js
    assert "Brainstorm-Dialog erscheint hier" in js
    assert "Arbeit starten" in js
