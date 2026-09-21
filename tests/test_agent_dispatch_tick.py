"""Dispatcher tick ends on GitHub effect or idle — not after grok --max-turns."""

from __future__ import annotations

import shlex
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
