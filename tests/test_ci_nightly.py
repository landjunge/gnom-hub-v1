"""Nightly GitHub Actions: scheduled tests plus mutation with cache recovery."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
NIGHTLY = (ROOT / ".github/workflows/mutation-nightly.yml").read_text(encoding="utf-8")
PAGES = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")


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


def test_actions_are_node24_majors():
    for text in (CI, NIGHTLY, PAGES):
        assert "actions/checkout@v4" not in text
        assert "actions/setup-python@v5" not in text
        assert "actions/cache@v4" not in text
    assert "actions/checkout@v5" in CI
    assert "actions/setup-python@v6" in CI
    assert "actions/cache@v5" in CI
    assert "astral-sh/ruff-action@v4" in CI
    assert "actions/setup-node@v5" in CI
    assert "persist-credentials: false" in CI


def test_pr_fail_fast_nightly_keeps_full_matrix():
    assert "fail-fast: ${{ github.event_name != 'schedule' }}" in CI
    assert "timeout-minutes: 12" in CI
    assert 'python -c "import sys"' in CI
    assert 'python -c "import sys"' in NIGHTLY
