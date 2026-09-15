"""R10: README twelve German sections, current desk words, no fake one-click."""

from pathlib import Path

from gnom_hub.system_ops import SystemOpsMixin

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
README_DE = (ROOT / "README_DE.md").read_text(encoding="utf-8")
HELP = SystemOpsMixin.help_text(object())


def test_readme_image_is_current_desk():
    img = ROOT / "docs/assets/desk-now.png"
    assert img.is_file()
    assert img.stat().st_size > 10_000
    assert "docs/assets/desk-now.png" in README


def test_readme_has_twelve_german_sections():
    for heading in (
        "1 · Was ist Gnom-Hub-V1?",
        "2 · Aktuelles Bild",
        "3 · Download und Installation",
        "4 · Erster Start",
        "5 · Senden, Arbeit starten und God-Mode",
        "6 · Agenten, Flags und Farben",
        "7 · Dateien, Memory und Behalten",
        "8 · Persönliche Daten",
        "9 · Update und Wiederherstellung",
        "10 · Typische Fehler",
        "11 · Entwicklerbereich",
        "12 · Reifegrad und bekannte Grenzen",
    ):
        assert heading in README, heading


def test_readme_uses_desk_verbs_not_execute():
    assert "Arbeit starten" in README
    assert "**Senden**" in README
    assert "Execute" not in README
    assert "Send+Exec" not in README
    assert "ein-klick" in README.lower()
    assert "kein ein-klick" in README.lower()
    assert "Terminal-Schnellinstallation" in README
    assert "WS-gnom-hub-v1" in README


def test_readme_de_points_to_readme():
    assert "README.md" in README_DE
    assert "Execute" not in README_DE


def test_help_has_update_topic_and_no_execute_pipeline():
    ids = [t["id"] for t in HELP["topics"]]
    assert "senden" in ids
    assert "arbeit" in ids
    assert "update" in ids
    assert "Execute" not in HELP["pipeline"]
    assert "Arbeit starten" in HELP["pipeline"]
    upd = next(t for t in HELP["topics"] if t["id"] == "update")
    assert "Klick" in upd["wozu"] or "klickst" in upd["wozu"]
    assert "main" in upd["nicht"]
