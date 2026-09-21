"""Dispatcher tick ends on GitHub effect or idle — not after grok --max-turns."""

from __future__ import annotations

import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from test_agent_dispatch import NOW, ad

PY = sys.executable


def _reviewer_job(pr: int = 145) -> ad.Job:
    return ad.Job(
        role="reviewer",
        reason="needs-review",
        pr=pr,
        repo="landjunge/gnom-hub-v1",
        base="baseline",
    )


def _hang_cmd(seconds: float) -> str:
    return f"{PY} -c 'import time; time.sleep({seconds})'"


def _events_script(path: Path, seconds: float, step: float = 0.05) -> str:
    path.write_text(
        "import time\n"
        f"end = time.monotonic() + {seconds}\n"
        "while time.monotonic() < end:\n"
        "    print('event', flush=True)\n"
        f"    time.sleep({step})\n",
        encoding="utf-8",
    )
    return f"{PY} {shlex.quote(str(path))}"


def test_github_effect_done_on_merged_pr() -> None:
    job = _reviewer_job()

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "closed", "merged": True}
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is True


def test_github_effect_done_false_while_pr_open() -> None:
    job = _reviewer_job()

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is False


def test_github_effect_done_on_completion_comment() -> None:
    job = ad.Job(
        role="test-agent",
        reason="baseline-moved",
        issue=105,
        repo="landjunge/gnom-hub-v1",
    )
    later = (NOW + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def github(method: str, url: str, token: str, payload):
        if "/comments" in url:
            return [
                {
                    "body": "**Test-Agent** nach Merge #145. 968 passed.",
                    "created_at": later,
                }
            ]
        if url.endswith("/issues/105"):
            return {"number": 105, "state": "open"}
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is True


def test_github_effect_ignores_other_role_comment_on_haupt() -> None:
    job = ad.Job(
        role="test-agent",
        reason="baseline-moved",
        issue=105,
        repo="landjunge/gnom-hub-v1",
    )
    later = (NOW + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def github(method: str, url: str, token: str, payload):
        if "/comments" in url:
            return [
                {
                    "body": "**Reviewer** #145: squash-merge nach baseline.",
                    "created_at": later,
                }
            ]
        if url.endswith("/issues/105"):
            return {"number": 105, "state": "open"}
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is False


def test_github_effect_done_on_closed_issue() -> None:
    job = ad.Job(
        role="builder",
        reason="open-teilaufgabe",
        issue=147,
        repo="landjunge/gnom-hub-v1",
    )

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/issues/147"):
            return {"number": 147, "state": "closed"}
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is True


def test_github_effect_done_on_new_changes_requested() -> None:
    job = _reviewer_job()
    later = (NOW + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        if url.endswith("/reviews"):
            return [{"state": "CHANGES_REQUESTED", "submitted_at": later}]
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is True


def test_run_agent_returns_after_simulated_merge() -> None:
    """Merge/Done must return without waiting out grok --max-turns (here: 8s hang)."""
    job = _reviewer_job()

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "closed", "merged": True}
        return []

    t0 = time.monotonic()
    how = ad.run_agent(
        job,
        "prompt",
        cmd=_hang_cmd(8),
        token="tok",
        github=github,
        poll_sec=0.05,
        idle_sec=60,
        now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
    )
    elapsed = time.monotonic() - t0
    assert how.startswith("cmd:")
    assert elapsed < 2.0


def test_run_agent_returns_after_simulated_done_comment() -> None:
    job = ad.Job(
        role="test-agent",
        reason="baseline-moved",
        issue=105,
        repo="landjunge/gnom-hub-v1",
    )
    later = "2026-09-21T10:00:30Z"

    def github(method: str, url: str, token: str, payload):
        if "/comments" in url:
            return [{"body": "**Test-Agent** nach Merge #145.", "created_at": later}]
        if url.endswith("/issues/105"):
            return {"number": 105, "state": "open"}
        return []

    t0 = time.monotonic()
    how = ad.run_agent(
        job,
        "prompt",
        cmd=_hang_cmd(8),
        token="tok",
        github=github,
        poll_sec=0.05,
        idle_sec=60,
        now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
    )
    elapsed = time.monotonic() - t0
    assert how.startswith("cmd:")
    assert elapsed < 2.0


def test_run_agent_does_not_kill_busy_tick(tmp_path: Path) -> None:
    """Events or descendant CPU keep the tick alive even with a short idle limit."""
    job = _reviewer_job()

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        return []

    duration = 0.7
    cmd = _events_script(tmp_path / "busy.py", duration)
    t0 = time.monotonic()
    how = ad.run_agent(
        job,
        "prompt",
        cmd=cmd,
        token="tok",
        github=github,
        cpu_of=lambda _pid: 40.0,
        poll_sec=0.05,
        idle_sec=0.15,
        now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
    )
    elapsed = time.monotonic() - t0
    assert how.startswith("cmd:")
    assert elapsed >= 0.45


def test_run_agent_keeps_cpu_busy_tick_without_events() -> None:
    job = _reviewer_job()

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        return []

    t0 = time.monotonic()
    how = ad.run_agent(
        job,
        "prompt",
        cmd=_hang_cmd(0.7),
        token="tok",
        github=github,
        cpu_of=lambda _pid: 25.0,
        poll_sec=0.05,
        idle_sec=0.15,
        now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
    )
    elapsed = time.monotonic() - t0
    assert how.startswith("cmd:")
    assert elapsed >= 0.45


def test_run_agent_returns_on_event_idle() -> None:
    job = _reviewer_job()

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        return []

    t0 = time.monotonic()
    how = ad.run_agent(
        job,
        "prompt",
        cmd=_hang_cmd(8),
        token="tok",
        github=github,
        cpu_of=lambda _pid: 0.0,
        poll_sec=0.05,
        idle_sec=0.2,
        now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
    )
    elapsed = time.monotonic() - t0
    assert how.startswith("cmd:")
    assert elapsed < 2.0


def test_priority_unchanged() -> None:
    assert ad.PRIORITY == (
        "review-fixes",
        "reviewer",
        "test-agent",
        "builder",
        "planer",
        "koordinator",
    )


def test_is_done_comment_role_and_generic() -> None:
    assert ad.is_done_comment("**Test-Agent** nach Merge", "test-agent") is True
    assert ad.is_done_comment("**Reviewer** #145", "reviewer") is True
    assert ad.is_done_comment("Planer: Zerlegung steht", "planer") is True
    assert ad.is_done_comment("**Koordinator-Meldung:**", "koordinator") is True
    assert ad.is_done_comment("Fixes #147", "builder") is True
    assert ad.is_done_comment("Closes #147", "builder") is True
    assert ad.is_done_comment("squash-merge nach baseline", "reviewer") is True
    assert ad.is_done_comment("fast-forward main", "reviewer") is True
    assert ad.is_done_comment("PR gemerged", "reviewer") is True
    assert ad.is_done_comment("Issue geschlossen", "builder") is True
    assert ad.is_done_comment("still working", "reviewer") is False


def test_is_done_comment_strict_role_ignores_generic() -> None:
    assert ad.is_done_comment("squash-merge", "test-agent", strict_role=True) is False
    assert ad.is_done_comment("**Test-Agent** ok", "test-agent", strict_role=True) is True


def test_tick_idle_sec_clamps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GNOM_TICK_IDLE_SEC", raising=False)
    assert ad.tick_idle_sec() == 20.0
    monkeypatch.setenv("GNOM_TICK_IDLE_SEC", "1")
    assert ad.tick_idle_sec() == 2.0
    monkeypatch.setenv("GNOM_TICK_IDLE_SEC", "999")
    assert ad.tick_idle_sec() == 120.0
    monkeypatch.setenv("GNOM_TICK_IDLE_SEC", "nope")
    assert ad.tick_idle_sec() == 20.0


def test_tick_poll_sec_clamps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GNOM_TICK_POLL_SEC", raising=False)
    assert ad.tick_poll_sec() == 2.0
    monkeypatch.setenv("GNOM_TICK_POLL_SEC", "0.01")
    assert ad.tick_poll_sec() == 0.2
    monkeypatch.setenv("GNOM_TICK_POLL_SEC", "99")
    assert ad.tick_poll_sec() == 30.0
    monkeypatch.setenv("GNOM_TICK_POLL_SEC", "x")
    assert ad.tick_poll_sec() == 2.0


def test_process_cpu_percent_nonpositive_pid() -> None:
    assert ad.process_cpu_percent(0) == 0.0
    assert ad.process_cpu_percent(-1) == 0.0


def test_process_cpu_percent_sums_descendants(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ad.subprocess,
        "check_output",
        lambda *args, **kwargs: "10 1 2.0\n11 10 3.0\n12 11 4.0\n",
    )
    assert ad.process_cpu_percent(10) == 9.0


def test_process_cpu_percent_unknown_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ad.subprocess, "check_output", lambda *args, **kwargs: "10 1 2.0\n")
    assert ad.process_cpu_percent(99) == 0.0


def test_process_cpu_percent_unreadable_is_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> str:
        raise OSError("ps")

    monkeypatch.setattr(ad.subprocess, "check_output", boom)
    assert ad.process_cpu_percent(10) == 100.0


def test_github_effect_false_without_token() -> None:
    called: list[str] = []

    def github(method: str, url: str, token: str, payload):
        called.append(url)
        return {"number": 145, "state": "closed", "merged": True}

    assert ad.github_effect_done(_reviewer_job(), "", NOW, github=github) is False
    assert called == []


def test_github_effect_done_on_closed_unmerged_pr() -> None:
    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "closed", "merged": False}
        return []

    assert ad.github_effect_done(_reviewer_job(), "tok", NOW, github=github) is True


def test_github_effect_ignores_old_changes_requested() -> None:
    earlier = (NOW - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        if url.endswith("/reviews"):
            return [{"state": "CHANGES_REQUESTED", "submitted_at": earlier}]
        return []

    assert ad.github_effect_done(_reviewer_job(), "tok", NOW, github=github) is False


def test_github_effect_changes_requested_without_timestamp() -> None:
    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        if url.endswith("/reviews"):
            return [{"state": "CHANGES_REQUESTED"}]
        return []

    assert ad.github_effect_done(_reviewer_job(), "tok", NOW, github=github) is True


def test_github_effect_done_on_pr_completion_comment() -> None:
    later = (NOW + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        if "/comments" in url:
            return [{"body": "**Reviewer** #145: kein Blocker.", "created_at": later}]
        return []

    assert ad.github_effect_done(_reviewer_job(), "tok", NOW, github=github) is True


def test_github_effect_ignores_comment_before_start() -> None:
    job = ad.Job(
        role="test-agent",
        reason="baseline-moved",
        issue=105,
        repo="landjunge/gnom-hub-v1",
    )
    earlier = (NOW - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def github(method: str, url: str, token: str, payload):
        if "/comments" in url:
            return [{"body": "**Test-Agent** nach Merge #145.", "created_at": earlier}]
        if url.endswith("/issues/105"):
            return {"number": 105, "state": "open"}
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is False


def test_github_effect_strict_haupt_ignores_generic_done() -> None:
    job = ad.Job(
        role="test-agent",
        reason="baseline-moved",
        issue=105,
        repo="landjunge/gnom-hub-v1",
    )
    later = (NOW + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def github(method: str, url: str, token: str, payload):
        if "/comments" in url:
            return [{"body": "squash-merge nach baseline.", "created_at": later}]
        if url.endswith("/issues/105"):
            return {"number": 105, "state": "open"}
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is False


def test_github_effect_generic_done_on_teilaufgabe() -> None:
    job = ad.Job(
        role="builder",
        reason="open-teilaufgabe",
        issue=147,
        repo="landjunge/gnom-hub-v1",
    )
    later = (NOW + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def github(method: str, url: str, token: str, payload):
        if "/comments" in url:
            return [{"body": "squash-merge nach baseline.", "created_at": later}]
        if url.endswith("/issues/147"):
            return {"number": 147, "state": "open"}
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is True


def test_github_effect_unparseable_comment_timestamp_counts() -> None:
    job = ad.Job(
        role="test-agent",
        reason="baseline-moved",
        issue=105,
        repo="landjunge/gnom-hub-v1",
    )

    def github(method: str, url: str, token: str, payload):
        if "/comments" in url:
            return [{"body": "**Test-Agent** nach Merge #145.", "created_at": "not-a-date"}]
        if url.endswith("/issues/105"):
            return {"number": 105, "state": "open"}
        return []

    assert ad.github_effect_done(job, "tok", NOW, github=github) is True


def test_github_effect_api_error_is_not_done() -> None:
    def github(method: str, url: str, token: str, payload):
        raise RuntimeError("403")

    assert ad.github_effect_done(_reviewer_job(), "tok", NOW, github=github) is False


def test_run_agent_missing_cmd_raises() -> None:
    with pytest.raises(RuntimeError, match="missing-cmd"):
        ad.run_agent(_reviewer_job(), "prompt", cmd="  ")


def test_run_agent_nonzero_exit_raises() -> None:
    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        return []

    with pytest.raises(subprocess.CalledProcessError):
        ad.run_agent(
            _reviewer_job(),
            "prompt",
            cmd=f"{PY} -c 'raise SystemExit(1)'",
            token="tok",
            github=github,
            poll_sec=0.05,
            idle_sec=60,
            now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
        )


def test_run_agent_keeps_event_busy_tick_without_cpu(tmp_path: Path) -> None:
    """Stdout events keep the tick alive even when descendant CPU is idle."""
    duration = 0.7
    cmd = _events_script(tmp_path / "busy.py", duration)

    def github(method: str, url: str, token: str, payload):
        if url.endswith("/pulls/145"):
            return {"number": 145, "state": "open", "merged": False}
        return []

    t0 = time.monotonic()
    how = ad.run_agent(
        _reviewer_job(),
        "prompt",
        cmd=cmd,
        token="tok",
        github=github,
        cpu_of=lambda _pid: 0.0,
        poll_sec=0.05,
        idle_sec=0.15,
        now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
    )
    elapsed = time.monotonic() - t0
    assert how.startswith("cmd:")
    assert elapsed >= 0.45
