"""Nightly GitHub Actions: scheduled tests plus mutation with cache recovery."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
NIGHTLY = (ROOT / ".github/workflows/mutation-nightly.yml").read_text(encoding="utf-8")


def test_ci_has_nightly_schedule_no_publish():
    assert 'cron: "12 3 * * *"' in CI or "cron: '12 3 * * *'" in CI
    assert "workflow_dispatch" in CI
    # scheduled CI must not gain a release job of its own
    assert "Create GitHub Release" in CI  # existing tag-only job
    assert "startsWith(github.ref, 'refs/tags/v')" in CI


def test_mutation_nightly_schedule_and_venv_guard():
    assert "cron:" in NIGHTLY
    assert "workflow_dispatch" in NIGHTLY
    assert "CACHE_SEED: v4" in NIGHTLY
    assert "Verify cached venv" in NIGHTLY
    assert "steps.verify-venv.outputs.broken" in NIGHTLY
    assert "Create GitHub Release" not in NIGHTLY
