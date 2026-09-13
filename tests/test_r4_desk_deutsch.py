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
    js = "".join(
        Path("src/gnom_hub/ui/static/parts/" + n).read_text(encoding="utf-8")
        for n in ("01-core-api.js", "02-speech.js")
    )
    assert "Brainstorm dialogue appears here" not in js
    assert "Empty — send" not in js
    assert "Noch keine Antwort" in js or "Brainstorm-Dialog erscheint hier" in js
    assert "reden" in js
    assert "Arbeit starten" in js
