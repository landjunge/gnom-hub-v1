"""R10: README and site slogan match the German desk (Arbeiter)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
SITE = (ROOT / "site/index.html").read_text(encoding="utf-8")


def test_readme_uses_arbeiter_not_worker_labels():
    assert "Arbeit starten heißt Arbeiter" in README
    assert "Arbeiter 1–4" in README
    assert "Worker 1–4" not in README
    assert "Worker-Lieferung" not in README
    assert "Arbeit starten heißt Worker" not in README


def test_site_slogan_arbeiter():
    assert "Arbeit starten heißt Arbeiter" in SITE
    assert "Arbeit starten heißt Worker" not in SITE
