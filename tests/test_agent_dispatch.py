"""Agent dispatcher — role pick and one-job-per-tick, no live GitHub."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agent_dispatch.py"


def _load():
    name = "gnom_agent_dispatch"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ad = _load()
NOW = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)


def _issue(number: int, *, labels: list[str] | None = None, hours_ago: float = 0.1) -> dict:
    updated = NOW - timedelta(hours=hours_ago)
    return {
        "number": number,
        "state": "open",
        "title": f"T{number}",
        "labels": [{"name": name} for name in (labels or ["teilaufgabe"])],
        "updated_at": updated.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _pr(number: int, title: str = "", sha: str = "abc") -> dict:
    return {
        "number": number,
        "title": title or f"PR {number}",
        "body": "",
        "head": {"sha": sha},
    }


def _snap(**kwargs) -> ad.Snapshot:
    data = {
        "teilaufgaben": [],
        "pulls": [],
        "reviews": {},
        "haupt": {"number": 105, "state": "open"},
        "baseline_sha": "base-sha",
        "now": NOW,
    }
    data.update(kwargs)
    return ad.Snapshot(**data)


def test_priority_chain_is_strict() -> None:
    """Review-Fixes → Reviewer → Test → Builder → Planer → Koordinator."""
    assert ad.PRIORITY == (
        "review-fixes",
        "reviewer",
        "test-agent",
        "builder",
        "planer",
        "koordinator",
    )
    snap = _snap(
        pulls=[
            _pr(1, "fixes (#10)", sha="aaa"),
            _pr(2, "other", sha="bbb"),
        ],
        reviews={
            1: [{"state": "CHANGES_REQUESTED", "submitted_at": "2026-09-20T13:00:00Z"}],
            2: [],
        },
        teilaufgaben=[
            _issue(10, labels=["teilaufgabe", "in-bearbeitung"]),
            _issue(11),
        ],
        baseline_sha="new-sha",
        haupt={"number": 105, "state": "open"},
    )
    state: dict = {"started": {}, "last_test_sha": "old-sha"}
    seen: list[tuple[str, str]] = []
    for _ in range(6):
        job = ad.pick_job(snap, state)
        if job is None:
            break
        seen.append((job.role, job.reason))
        ad.mark_started(state, job, "ok", NOW)
    assert seen[0] == ("builder", "changes-requested")
    assert seen[1] == ("reviewer", "needs-review")
    assert seen[2] == ("test-agent", "baseline-moved")
    assert seen[3] == ("builder", "open-teilaufgabe")
    # Planer only when the teilaufgabe list is empty.
    empty = _snap(
        pulls=[],
        teilaufgaben=[],
        baseline_sha="new-sha",
        haupt={"number": 105, "state": "open"},
    )
    plan = ad.pick_job(empty, {"started": {}, "last_test_sha": "new-sha"})
    assert plan is not None and plan.role == "planer"
    wait = _snap(
        pulls=[_pr(2, "other", sha="bbb")],
        reviews={2: [{"state": "COMMENTED", "submitted_at": "2026-09-20T15:00:00Z"}]},
        teilaufgaben=[_issue(10, labels=["teilaufgabe", "in-bearbeitung"])],
        baseline_sha="new-sha",
        haupt={"number": 105, "state": "open"},
    )
    wait_state: dict = {"started": {}, "last_test_sha": "new-sha"}
    first = ad.pick_job(wait, wait_state)
    assert first is not None and first.role == "reviewer"
    ad.mark_started(wait_state, first, "ok", NOW)
    coord = ad.pick_job(wait, wait_state)
    assert coord is not None and coord.role == "koordinator"


def test_changes_requested_starts_builder_not_reviewer() -> None:
    snap = _snap(
        pulls=[_pr(109, "fix honesty (#106)", sha="deadbeef")],
        reviews={109: [{"state": "CHANGES_REQUESTED", "submitted_at": "2026-09-20T13:18:53Z"}]},
        teilaufgaben=[_issue(106, labels=["teilaufgabe", "in-bearbeitung"]), _issue(107)],
    )
    job = ad.pick_job(snap, {"started": {}})
    assert job is not None
    assert job.role == "builder"
    assert job.pr == 109
    assert job.reason == "changes-requested"


def test_open_pr_without_review_starts_reviewer() -> None:
    snap = _snap(pulls=[_pr(113, sha="cafe")], reviews={113: []})
    job = ad.pick_job(snap, {"started": {}})
    assert job is not None
    assert job.role == "reviewer"
    assert job.pr == 113
    assert job.reason == "needs-review"


def test_approved_open_pr_starts_reviewer_merge() -> None:
    snap = _snap(
        pulls=[_pr(114, sha="abcd")],
        reviews={114: [{"state": "APPROVED", "submitted_at": "2026-09-20T15:00:00Z"}]},
    )
    job = ad.pick_job(snap, {"started": {}})
    assert job is not None
    assert job.role == "reviewer"
    assert job.reason == "merge-approved"


def test_open_teilaufgabe_starts_builder_when_no_pr() -> None:
    snap = _snap(teilaufgaben=[_issue(107)], pulls=[])
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "builder"
    assert job.issue == 107
    assert job.reason == "open-teilaufgabe"


def test_in_bearbeitung_is_skipped_until_stale() -> None:
    snap = _snap(
        teilaufgaben=[_issue(106, labels=["teilaufgabe", "in-bearbeitung"], hours_ago=0.2)]
    )
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is None


def test_stale_in_bearbeitung_retries_builder() -> None:
    snap = _snap(
        pulls=[],
        teilaufgaben=[_issue(106, labels=["teilaufgabe", "in-bearbeitung"], hours_ago=3)],
        baseline_sha="base-sha",
    )
    state = {"started": {}, "last_test_sha": "base-sha"}
    job = ad.pick_job(snap, state)
    assert job is not None
    assert job.role == "builder"
    assert job.issue == 106
    assert job.reason == "stale-retry"


def test_planer_when_haupt_open_and_no_teilaufgaben() -> None:
    snap = _snap(teilaufgaben=[], pulls=[], baseline_sha="base-sha")
    state = {"started": {}, "last_test_sha": "base-sha"}
    job = ad.pick_job(snap, state)
    assert job is not None
    assert job.role == "planer"
    assert job.issue == 105


def test_test_agent_when_baseline_moved() -> None:
    snap = _snap(teilaufgaben=[], pulls=[], baseline_sha="new-sha")
    state = {"started": {}, "last_test_sha": "old-sha"}
    job = ad.pick_job(snap, state)
    assert job is not None
    assert job.role == "test-agent"
    assert job.sha == "new-sha"


def test_one_job_per_tick_prefers_review_fixes(tmp_path: Path) -> None:
    launched: list[str] = []

    def launch(role: str, prompt: str, env: dict) -> str:
        launched.append(role)
        assert "PR #109" in prompt or "Review-Kommentare" in prompt
        return "cmd:ok"

    snap = _snap(
        pulls=[_pr(109, "fix (#106)")],
        reviews={109: [{"state": "CHANGES_REQUESTED", "submitted_at": "2026-09-20T13:18:53Z"}]},
        teilaufgaben=[_issue(107)],
        baseline_sha="base-sha",
    )
    action = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=tmp_path / "state.json",
        agents_dir=ROOT / "agents",
        snapshot=snap,
        launch=launch,
        now=NOW,
    )
    assert action == "started"
    assert launched == ["builder"]


def _seed_tested(path: Path) -> None:
    ad.save_state(path, {"started": {}, "last_test_sha": "base-sha"})


def test_dry_run_does_not_launch(tmp_path: Path) -> None:
    launched: list[str] = []
    snap = _snap(teilaufgaben=[_issue(107)], pulls=[], baseline_sha="base-sha")
    state_path = tmp_path / "state.json"
    _seed_tested(state_path)
    action = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=state_path,
        agents_dir=ROOT / "agents",
        dry_run=True,
        snapshot=snap,
        launch=lambda *_a, **_k: launched.append("x") or "cmd",
        now=NOW,
    )
    assert action == "dry-run"
    assert launched == []
    saved = ad.load_state(state_path)
    assert saved["started"] == {}


def test_launch_failed_does_not_record_started(tmp_path: Path) -> None:
    def boom(role: str, prompt: str, env: dict) -> str:
        raise RuntimeError("no-grok")

    snap = _snap(teilaufgaben=[_issue(107)], pulls=[], baseline_sha="base-sha")
    state_path = tmp_path / "state.json"
    _seed_tested(state_path)
    action = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=state_path,
        agents_dir=ROOT / "agents",
        snapshot=snap,
        launch=boom,
        now=NOW,
    )
    assert action == "launch-failed"
    assert ad.load_state(state_path)["started"] == {}


def test_started_ttl_prevents_double_start(tmp_path: Path) -> None:
    launched: list[str] = []
    snap = _snap(teilaufgaben=[_issue(107)], pulls=[], baseline_sha="base-sha")
    state_path = tmp_path / "state.json"
    _seed_tested(state_path)
    first = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=state_path,
        agents_dir=ROOT / "agents",
        snapshot=snap,
        launch=lambda *_a, **_k: launched.append("1") or "ok",
        now=NOW,
    )
    second = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=state_path,
        agents_dir=ROOT / "agents",
        snapshot=snap,
        launch=lambda *_a, **_k: launched.append("2") or "ok",
        now=NOW,
    )
    assert first == "started"
    assert second != "started"
    assert launched == ["1"]


def test_disabled_short_circuits(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GNOM_AGENT_DISPATCH", "0")
    action = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=tmp_path / "s.json",
        agents_dir=ROOT / "agents",
    )
    assert action == "disabled"


def test_no_token_does_not_fetch(tmp_path: Path) -> None:
    action = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="",
        state_path=tmp_path / "s.json",
        agents_dir=ROOT / "agents",
    )
    assert action == "no-token"
