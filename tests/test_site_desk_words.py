"""Product site uses desk verbs and honest terminal install, not a fake release download."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def test_index_has_terminal_install_under_logo():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert "Execute" not in html
    assert "Arbeit starten" in html
    assert "Senden" in html
    assert "Terminal-Schnellinstallation" in html
    assert "kein ein-klick" in html.lower()
    assert "scripts/get.sh" in html
    assert "releases/latest" not in html
    assert 'href="#install"' in html


def test_de_install_is_terminal_not_one_click():
    html = (SITE / "de.html").read_text(encoding="utf-8")
    assert "Execute" not in html
    assert "Arbeit starten" in html
    assert "Terminal-Schnellinstallation" in html
    assert "scripts/get.sh" in html
    assert "desk-now.png" in html
    assert (SITE / "assets/desk-now.png").is_file()


def test_remaining_site_pages_drop_execute():
    for rel in (
        "llms.txt",
        "ecosystem.html",
        "blog/launch.html",
        "press/index.html",
    ):
        text = (SITE / rel).read_text(encoding="utf-8")
        assert "Execute" not in text, rel
        assert "Arbeit starten" in text, rel
