"""R10: README, site, install and help say Arbeiter like the desk."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
SITE = (ROOT / "site/index.html").read_text(encoding="utf-8")
GET = (ROOT / "scripts/get.sh").read_text(encoding="utf-8")
INSTALL = (ROOT / "docs/INSTALL_SIMPLE.md").read_text(encoding="utf-8")
README_DE = (ROOT / "README_DE.md").read_text(encoding="utf-8")
HELP = (ROOT / "src/gnom_hub/system_ops.py").read_text(encoding="utf-8")
TIPS = (ROOT / "src/gnom_hub/ui/tooltips.py").read_text(encoding="utf-8")
NIGHTLY = (ROOT / ".github/workflows/mutation-nightly.yml").read_text(encoding="utf-8")


def test_readme_uses_arbeiter_not_worker_labels():
    assert "Arbeit starten heißt Arbeiter" in README
    assert "Arbeiter 1–4" in README
    assert "Worker 1–4" not in README
    assert "Worker-Lieferung" not in README
    assert "Arbeit starten heißt Worker" not in README


def test_site_slogan_arbeiter():
    assert "Arbeit starten heißt Arbeiter" in SITE
    assert "Arbeit starten heißt Worker" not in SITE


def test_install_paths_say_arbeiter():
    assert "Arbeit starten = Arbeiter" in GET
    assert "Arbeit starten = Arbeiter" in INSTALL
    assert "Arbeit starten = Arbeiter" in README_DE
    assert "Arbeit starten = Worker" not in GET
    assert "Arbeit starten = Worker" not in INSTALL
    assert "Arbeit starten = Worker" not in README_DE


def test_help_and_tooltips_say_arbeiter():
    assert "Arbeit starten = Arbeiter" in HELP
    assert "Arbeiter (1–4)" in HELP
    assert "Arbeit starten = Worker" not in HELP
    assert "Arbeit starten = Arbeiter" in TIPS
    assert "Arbeit starten = Worker" not in TIPS


def test_mutation_nightly_recovers_broken_venv():
    assert "Verify cached venv" in NIGHTLY
    assert ".venv/bin/python" in NIGHTLY
    assert "steps.verify-venv.outputs.broken" in NIGHTLY
