"""Visible human workspace shell — German labels, no Send+Exec."""

from __future__ import annotations

from pathlib import Path

HTML = Path("src/gnom_hub/ui/static/index.html").read_text(encoding="utf-8")


def test_visible_region_titles_are_german() -> None:
    assert "Rückfragen und Entscheidungen" in HTML
    assert "Gespräch und Auftrag" in HTML
    assert "Arbeit und Ergebnisse" in HTML


def test_empty_states_explain_the_three_regions() -> None:
    assert "Hier erscheinen Rückfragen, wenn Gnom deine Hilfe braucht." in HTML
    assert "Beschreibe hier, was du machen möchtest." in HTML
    assert "Hier siehst du laufende Arbeit und fertige Ergebnisse." in HTML


def test_main_actions_are_german_and_send_exec_is_gone() -> None:
    assert ">Nachricht senden<" in HTML
    assert ">Arbeit starten<" in HTML
    assert ">Arbeit abbrechen<" in HTML
    assert 'id="btn-send-exec"' not in HTML
    assert "Send+Exec" not in HTML
