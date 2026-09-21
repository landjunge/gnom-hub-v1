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


def _pr(
    number: int,
    title: str = "",
    sha: str = "abc",
    *,
    repo: str = "",
    base: str = "",
    ci: str = "",
    draft: bool | None = None,
    mergeable: bool | None = None,
) -> dict:
    pr: dict = {
        "number": number,
        "title": title or f"PR {number}",
        "body": "",
        "head": {"sha": sha},
    }
    if repo:
        pr["_repo"] = repo
        pr["base"] = {
            "ref": base or "main",
            "repo": {"full_name": repo},
        }
        pr["html_url"] = f"https://github.com/{repo}/pull/{number}"
    elif base:
        pr["_base"] = base
        pr["base"] = {"ref": base}
    if draft is not None:
        pr["draft"] = draft
    if mergeable is not None:
        pr["mergeable"] = mergeable
    if ci:
        pr["_ci"] = ci
        if ci.lower() == "success":
            pr["statusCheckRollup"] = [{"state": "SUCCESS"}]
        elif ci.lower() in ("failure", "error"):
            pr["statusCheckRollup"] = [{"state": "FAILURE"}]
    return pr


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


def test_comment_plus_unmergeable_starts_builder_not_reviewer() -> None:
    snap = _snap(
        pulls=[
            _pr(
                26,
                "harden",
                sha="toll",
                repo="landjunge/tollgate",
                base="main",
                mergeable=False,
            )
        ],
        reviews={
            ("landjunge/tollgate", 26): [
                {"state": "COMMENTED", "submitted_at": "2026-09-21T03:52:24Z"}
            ]
        },
        teilaufgaben=[_issue(139)],
        baseline_sha="base-sha",
    )
    state: dict = {"started": {}, "last_test_sha": "base-sha"}
    job = ad.pick_job(snap, state)
    assert job is not None
    assert job.role == "builder"
    assert job.reason == "changes-requested"
    assert job.pr == 26
    assert job.repo == "landjunge/tollgate"
    ad.mark_started(state, job, "ok", NOW)
    nxt = ad.pick_job(snap, state)
    assert nxt is not None
    assert nxt.role == "builder"
    assert nxt.reason == "open-teilaufgabe"
    assert nxt.issue == 139


def test_comment_plus_draft_failed_check_starts_builder() -> None:
    snap = _snap(
        pulls=[
            _pr(
                14,
                "finding",
                sha="lab",
                repo="landjunge/agent-authority-lab",
                base="master",
                ci="failure",
                draft=True,
            )
        ],
        reviews={
            ("landjunge/agent-authority-lab", 14): [
                {"state": "COMMENT", "submitted_at": "2026-09-21T04:27:57Z"}
            ]
        },
        teilaufgaben=[_issue(139)],
        baseline_sha="base-sha",
    )
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "builder"
    assert job.reason == "changes-requested"
    assert job.pr == 14
    assert job.repo == "landjunge/agent-authority-lab"


def test_comment_without_blocker_stays_reviewer() -> None:
    snap = _snap(
        pulls=[
            _pr(
                57,
                "p10",
                sha="ok",
                repo="landjunge/threaddesk",
                base="main",
                ci="success",
                mergeable=True,
                draft=False,
            )
        ],
        reviews={
            ("landjunge/threaddesk", 57): [
                {"state": "COMMENTED", "submitted_at": "2026-09-21T04:11:29Z"}
            ]
        },
        teilaufgaben=[_issue(139)],
        baseline_sha="base-sha",
    )
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "reviewer"
    assert job.pr == 57


def test_comment_blocker_beats_unreviewed_pr() -> None:
    snap = _snap(
        pulls=[
            _pr(215, "feat", sha="pass", repo="landjunge/4AllPass", base="main", ci="success"),
            _pr(
                14,
                "finding",
                sha="lab",
                repo="landjunge/agent-authority-lab",
                base="master",
                ci="failure",
                draft=True,
            ),
        ],
        reviews={
            ("landjunge/4AllPass", 215): [],
            ("landjunge/agent-authority-lab", 14): [
                {"state": "COMMENTED", "submitted_at": "2026-09-21T04:27:57Z"}
            ],
        },
        teilaufgaben=[_issue(139)],
        baseline_sha="base-sha",
    )
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "builder"
    assert job.reason == "changes-requested"
    assert job.pr == 14


def test_dry_run_comment_plus_red_ci_picks_builder(tmp_path: Path, capsys) -> None:
    snap = _snap(
        pulls=[
            _pr(
                14,
                "finding",
                sha="lab",
                repo="landjunge/agent-authority-lab",
                base="master",
                ci="failure",
                draft=True,
            )
        ],
        reviews={
            ("landjunge/agent-authority-lab", 14): [
                {"state": "COMMENTED", "submitted_at": "2026-09-21T04:27:57Z"}
            ]
        },
        teilaufgaben=[_issue(139)],
        baseline_sha="base-sha",
    )
    action = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=tmp_path / "state.json",
        agents_dir=ROOT / "agents",
        dry_run=True,
        snapshot=snap,
        now=NOW,
    )
    assert action == "dry-run"
    out = capsys.readouterr().out
    assert "role=builder" in out
    assert "changes-requested" in out
    assert "landjunge/agent-authority-lab#14" in out


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


def test_default_repos_are_the_five_products() -> None:
    names = [spec.repo for spec in ad.DEFAULT_REPOS]
    assert names == [
        "landjunge/gnom-hub-v1",
        "landjunge/4AllPass",
        "landjunge/tollgate",
        "landjunge/threaddesk",
        "landjunge/agent-authority-lab",
    ]
    by_repo = {spec.repo: spec.bases for spec in ad.DEFAULT_REPOS}
    assert by_repo["landjunge/gnom-hub-v1"] == ("baseline", "main")
    assert by_repo["landjunge/4AllPass"] == ("main",)
    assert by_repo["landjunge/agent-authority-lab"] == ("master",)


def test_repos_from_env_defaults_and_override(monkeypatch) -> None:
    monkeypatch.delenv("GNOM_GITHUB_REPOS", raising=False)
    assert ad.repos_from_env() == ad.DEFAULT_REPOS
    monkeypatch.setenv(
        "GNOM_GITHUB_REPOS",
        "landjunge/4AllPass:main, acme/lab:master",
    )
    specs = ad.repos_from_env()
    assert specs == (
        ad.RepoSpec("landjunge/4AllPass", ("main",)),
        ad.RepoSpec("acme/lab", ("master",)),
    )
    monkeypatch.setenv("GNOM_GITHUB_REPOS", "landjunge/gnom-hub-v1")
    hub = ad.repos_from_env()
    assert hub == (ad.RepoSpec("landjunge/gnom-hub-v1", ("baseline", "main")),)


def test_fourallpass_green_ci_pr_is_seen_by_reviewer() -> None:
    """A 4AllPass PR with green CI is a reviewer job, ahead of a home teilaufgabe."""
    snap = _snap(
        pulls=[
            _pr(
                215,
                "feat g5",
                sha="2fc8830",
                repo="landjunge/4AllPass",
                base="main",
                ci="success",
            )
        ],
        reviews={215: []},
        teilaufgaben=[_issue(133)],
        baseline_sha="base-sha",
    )
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "reviewer"
    assert job.reason == "needs-review"
    assert job.pr == 215
    assert job.repo == "landjunge/4AllPass"
    assert job.base == "main"


def test_home_changes_requested_beats_other_repo_review() -> None:
    snap = _snap(
        pulls=[
            _pr(9, "fix (#133)", sha="home", repo="landjunge/gnom-hub-v1", base="baseline"),
            _pr(
                215,
                "feat",
                sha="pass",
                repo="landjunge/4AllPass",
                base="main",
                ci="success",
            ),
        ],
        reviews={
            ("landjunge/gnom-hub-v1", 9): [
                {"state": "CHANGES_REQUESTED", "submitted_at": "2026-09-20T13:00:00Z"}
            ],
            ("landjunge/4AllPass", 215): [],
        },
        teilaufgaben=[_issue(133)],
        baseline_sha="base-sha",
    )
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "builder"
    assert job.reason == "changes-requested"
    assert job.repo == "landjunge/gnom-hub-v1"
    assert job.pr == 9


def test_same_pr_number_in_two_repos_does_not_collide() -> None:
    snap = _snap(
        pulls=[
            _pr(1, sha="a", repo="landjunge/4AllPass", base="main", ci="success"),
            _pr(1, sha="b", repo="landjunge/tollgate", base="main"),
        ],
        reviews={
            ("landjunge/4AllPass", 1): [
                {"state": "CHANGES_REQUESTED", "submitted_at": "2026-09-20T13:00:00Z"}
            ],
            ("landjunge/tollgate", 1): [],
        },
        baseline_sha="base-sha",
    )
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "builder"
    assert job.reason == "changes-requested"
    assert job.repo == "landjunge/4AllPass"
    assert job.pr == 1
    state = {"started": {}, "last_test_sha": "base-sha"}
    ad.mark_started(state, job, "ok", NOW)
    nxt = ad.pick_job(snap, state)
    assert nxt is not None
    assert nxt.role == "reviewer"
    assert nxt.repo == "landjunge/tollgate"
    assert nxt.pr == 1


def test_dry_run_lists_prs_from_product_repos(tmp_path: Path, capsys) -> None:
    snap = _snap(
        pulls=[
            _pr(11, repo="landjunge/4AllPass", base="main", ci="success"),
            _pr(22, repo="landjunge/tollgate", base="main"),
            _pr(33, repo="landjunge/threaddesk", base="main"),
            _pr(44, repo="landjunge/agent-authority-lab", base="master"),
        ],
        reviews={11: [], 22: [], 33: [], 44: []},
        baseline_sha="base-sha",
    )
    action = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=tmp_path / "state.json",
        agents_dir=ROOT / "agents",
        dry_run=True,
        snapshot=snap,
        repos=ad.DEFAULT_REPOS,
        now=NOW,
    )
    assert action == "dry-run"
    out = capsys.readouterr().out
    assert "landjunge/4AllPass#11" in out
    assert "ci=success" in out
    assert "landjunge/tollgate#22" in out
    assert "landjunge/threaddesk#33" in out
    assert "landjunge/agent-authority-lab#44" in out
    assert "seen-pr" in out
    assert "watch" in out
    assert "landjunge/4AllPass" in out
    assert "landjunge/tollgate" in out
    assert "landjunge/threaddesk" in out
    assert "landjunge/agent-authority-lab" in out


def test_collect_snapshot_watches_all_default_repos() -> None:
    seen_urls: list[str] = []

    def github(method: str, url: str, token: str, payload):
        seen_urls.append(url)
        if "/4AllPass/pulls?" in url:
            return [
                {
                    "number": 215,
                    "title": "g5",
                    "body": "",
                    "head": {"sha": "abc"},
                    "base": {"ref": "main", "repo": {"full_name": "landjunge/4AllPass"}},
                }
            ]
        if "/pulls/" in url and url.endswith("/reviews"):
            return []
        if "/issues?" in url:
            return [{"number": 133, "title": "T133", "labels": [{"name": "teilaufgabe"}]}]
        if f"/issues/{ad.HAUPT_ISSUE}" in url:
            return {"number": ad.HAUPT_ISSUE, "state": "open"}
        if "/git/ref/heads/" in url:
            return {"object": {"sha": "base-sha"}}
        if "/pulls?" in url:
            return []
        return []

    snap = ad.collect_snapshot(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        github=github,
        repos=ad.DEFAULT_REPOS,
        now=NOW,
    )
    watched = {url for url in seen_urls if "/pulls?" in url}
    assert any("repos/landjunge/gnom-hub-v1/pulls?" in u and "base=baseline" in u for u in watched)
    assert any("repos/landjunge/gnom-hub-v1/pulls?" in u and "base=main" in u for u in watched)
    assert any("repos/landjunge/4AllPass/pulls?" in u for u in watched)
    assert any("repos/landjunge/tollgate/pulls?" in u for u in watched)
    assert any("repos/landjunge/threaddesk/pulls?" in u for u in watched)
    assert any("repos/landjunge/agent-authority-lab/pulls?" in u for u in watched)
    assert len(snap.pulls) == 1
    assert ad.pr_repo(snap.pulls[0]) == "landjunge/4AllPass"
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "reviewer"
    assert job.repo == "landjunge/4AllPass"
    assert job.pr == 215


def test_watch_failed_skips_repo_and_keeps_others() -> None:
    def github(method: str, url: str, token: str, payload):
        if "/tollgate/pulls?" in url:
            raise RuntimeError("GitHub GET tollgate -> 404: missing")
        if "/4AllPass/pulls?" in url:
            return [
                {
                    "number": 7,
                    "title": "ok",
                    "body": "",
                    "head": {"sha": "fff"},
                    "base": {"ref": "main", "repo": {"full_name": "landjunge/4AllPass"}},
                }
            ]
        if "/pulls/" in url and url.endswith("/reviews"):
            return []
        if "/issues?" in url:
            return []
        if f"/issues/{ad.HAUPT_ISSUE}" in url:
            return {"number": ad.HAUPT_ISSUE, "state": "open"}
        if "/git/ref/heads/" in url:
            return {"object": {"sha": "base-sha"}}
        if "/pulls?" in url:
            return []
        return []

    snap = ad.collect_snapshot(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        github=github,
        repos=ad.DEFAULT_REPOS,
        now=NOW,
    )
    assert [ad.pr_repo(pr) for pr in snap.pulls] == ["landjunge/4AllPass"]
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None and job.repo == "landjunge/4AllPass"


def test_parse_repo_specs_plus_and_pipe_bases() -> None:
    plus = ad.parse_repo_specs("landjunge/gnom-hub-v1:baseline+main, landjunge/4AllPass:main")
    assert plus == (
        ad.RepoSpec("landjunge/gnom-hub-v1", ("baseline", "main")),
        ad.RepoSpec("landjunge/4AllPass", ("main",)),
    )
    pipe = ad.parse_repo_specs("acme/lab:master|dev")
    assert pipe == (ad.RepoSpec("acme/lab", ("master", "dev")),)


def test_collect_snapshot_dedupes_same_pr_on_two_bases() -> None:
    pulls_calls: list[str] = []

    def github(method: str, url: str, token: str, payload):
        if "/pulls?" in url:
            pulls_calls.append(url)
            return [
                {
                    "number": 9,
                    "title": "x",
                    "body": "",
                    "head": {"sha": "aaa"},
                    "base": {
                        "ref": "baseline",
                        "repo": {"full_name": "landjunge/gnom-hub-v1"},
                    },
                }
            ]
        if url.endswith("/reviews"):
            return []
        if "/issues?" in url:
            return []
        if f"/issues/{ad.HAUPT_ISSUE}" in url:
            return {"number": ad.HAUPT_ISSUE, "state": "open"}
        if "/git/ref/heads/" in url:
            return {"object": {"sha": "base-sha"}}
        return []

    snap = ad.collect_snapshot(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        github=github,
        repos=(ad.RepoSpec("landjunge/gnom-hub-v1", ("baseline", "main")),),
        now=NOW,
    )
    assert len(pulls_calls) == 2
    assert any("base=baseline" in url for url in pulls_calls)
    assert any("base=main" in url for url in pulls_calls)
    assert len(snap.pulls) == 1
    assert snap.pulls[0]["number"] == 9


def test_collect_snapshot_enriches_mergeable_and_failed_checks() -> None:
    seen: list[str] = []

    def github(method: str, url: str, token: str, payload):
        seen.append(url)
        if "/pulls?" in url:
            return [
                {
                    "number": 14,
                    "title": "finding",
                    "body": "",
                    "draft": True,
                    "mergeable": None,
                    "head": {"sha": "0de8a99"},
                    "base": {
                        "ref": "master",
                        "repo": {"full_name": "landjunge/agent-authority-lab"},
                    },
                }
            ]
        if url.endswith("/reviews"):
            return [{"state": "COMMENTED", "submitted_at": "2026-09-21T04:27:57Z"}]
        if url.endswith("/pulls/14"):
            return {
                "number": 14,
                "draft": True,
                "mergeable": True,
                "mergeable_state": "unstable",
            }
        if url.endswith("/check-runs"):
            return {
                "check_runs": [
                    {"name": "test", "status": "completed", "conclusion": "failure"},
                    {
                        "name": "Analyze (python)",
                        "status": "completed",
                        "conclusion": "success",
                    },
                ]
            }
        if "/issues?" in url:
            return []
        if f"/issues/{ad.HAUPT_ISSUE}" in url:
            return {"number": ad.HAUPT_ISSUE, "state": "open"}
        if "/git/ref/heads/" in url:
            return {"object": {"sha": "base-sha"}}
        return []

    snap = ad.collect_snapshot(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        github=github,
        repos=(ad.RepoSpec("landjunge/agent-authority-lab", ("master",)),),
        now=NOW,
    )
    assert len(snap.pulls) == 1
    pr = snap.pulls[0]
    assert pr["mergeable"] is True
    assert pr["draft"] is True
    assert ad.pr_ci(pr) == "failure"
    assert any(url.endswith("/pulls/14") for url in seen)
    assert any(url.endswith("/check-runs") for url in seen)
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "builder"
    assert job.reason == "changes-requested"
    assert job.pr == 14
    assert job.repo == "landjunge/agent-authority-lab"


def test_collect_snapshot_loads_merge_conflict_for_comment() -> None:
    def github(method: str, url: str, token: str, payload):
        if "/pulls?" in url:
            return [
                {
                    "number": 26,
                    "title": "harden",
                    "body": "",
                    "draft": False,
                    "mergeable": None,
                    "head": {"sha": "abc"},
                    "base": {
                        "ref": "main",
                        "repo": {"full_name": "landjunge/tollgate"},
                    },
                }
            ]
        if url.endswith("/reviews"):
            return [{"state": "COMMENTED", "submitted_at": "2026-09-21T03:52:24Z"}]
        if url.endswith("/pulls/26"):
            return {
                "number": 26,
                "draft": False,
                "mergeable": False,
                "mergeable_state": "dirty",
            }
        if url.endswith("/check-runs"):
            return {"check_runs": []}
        if "/issues?" in url:
            return []
        if f"/issues/{ad.HAUPT_ISSUE}" in url:
            return {"number": ad.HAUPT_ISSUE, "state": "open"}
        if "/git/ref/heads/" in url:
            return {"object": {"sha": "base-sha"}}
        return []

    snap = ad.collect_snapshot(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        github=github,
        repos=(ad.RepoSpec("landjunge/tollgate", ("main",)),),
        now=NOW,
    )
    assert snap.pulls[0]["mergeable"] is False
    job = ad.pick_job(snap, {"started": {}, "last_test_sha": "base-sha"})
    assert job is not None
    assert job.role == "builder"
    assert job.reason == "changes-requested"
    assert job.pr == 26
    assert job.repo == "landjunge/tollgate"


def test_launch_role_sets_repo_and_base_env(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs.get("env")
        captured["cwd"] = kwargs.get("cwd")

    monkeypatch.setattr(ad.subprocess, "run", fake_run)
    job = ad.Job(
        role="reviewer",
        reason="needs-review",
        pr=215,
        sha="2fc8830dead",
        repo="landjunge/4AllPass",
        base="main",
    )
    how = ad.launch_role(job, "prompt-text", cmd="true", cwd=tmp_path)
    assert how == "cmd:true"
    env = captured["env"]
    assert env["GNOM_AGENT_ROLE"] == "reviewer"
    assert env["GNOM_GITHUB_REPO"] == "landjunge/4AllPass"
    assert env["GNOM_JOB_BASE"] == "main"
    assert env["PR_NUMBER"] == "215"
    assert env["GNOM_JOB_SHA"] == "2fc8830dead"
    assert env["GNOM_JOB_REASON"] == "needs-review"
    assert captured["cwd"] == str(tmp_path)
    assert captured["argv"] == ["true"]
