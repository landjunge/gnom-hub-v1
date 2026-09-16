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


def test_de_tooltips_have_no_execute():
    for key, langs in TOOLTIPS.items():
        de = langs["de"]
        blob = " ".join(de.values())
        assert "Execute" not in blob, key
        assert "Worker-Ergebnisse" not in blob, key


def test_skills_modal_is_german():
    html = Path("src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")
    assert "Markdown-Playbooks für Agenten" in html
    assert ">Neu laden<" in html
    assert ">Installieren<" in html
    assert "Lokaler Ordner zum Installieren" in html
    assert "Katalog…" in html
    assert "last Execute" not in html
    assert "Destillieren + Arbeiter" in html
