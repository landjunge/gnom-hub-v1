"""Polling daemon for open teilaufgabe issues — no live GitHub."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "poll_teilaufgaben.py"
OK_CMD = f"{sys.executable} -c pass"


def _load():
    name = "gnom_poll_teilaufgaben"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


poll = _load()


def _issue(number: int, *, labels: list[str] | None = None, title: str = "T"):
    return {
        "number": number,
        "state": "open",
        "title": title,
        "labels": [{"name": name} for name in (labels or ["teilaufgabe"])],
    }


def test_interval_default_is_between_30_and_60() -> None:
    assert 30 <= poll.DEFAULT_INTERVAL <= 60


def test_already_started_on_in_bearbeitung() -> None:
    issue = _issue(106, labels=["teilaufgabe", "in-bearbeitung"])
    assert poll.already_started(issue, {"started": {}}) is True


def test_already_started_on_state_file() -> None:
    issue = _issue(108)
    state = {"started": {"108": {"at": "2026-09-20T12:00:00Z"}}}
    assert poll.already_started(issue, state) is True
    assert poll.already_started(_issue(107), state) is False


def test_already_started_on_claim_comment() -> None:
    issue = _issue(108)
    comments = [{"body": poll.CLAIM_MARKER + "\nBuilder-Poll claimt Issue #108."}]
    assert poll.already_started(issue, {"started": {}}, comments) is True


def test_missing_builder_cmd_does_not_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GNOM_BUILDER_CMD", raising=False)
    state_path = tmp_path / "state.json"
    action = poll.process_issue(
        _issue(108),
        repo="landjunge/gnom-hub-v1",
        token="",
        state={"started": {}},
        state_path=state_path,
        prompt_path=tmp_path / "missing.md",
        dry_run=False,
    )
    assert action == poll.MISSING_CMD
    assert not state_path.exists()


def test_poll_once_missing_env_returns_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GNOM_BUILDER_CMD", raising=False)
    actions = poll.poll_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=tmp_path / "state.json",
        prompt_path=tmp_path / "missing.md",
        list_issues=lambda *_: [_issue(106), _issue(107)],
    )
    assert actions == [poll.MISSING_CMD]


def test_double_claim_second_issue_skipped(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state: dict = {"started": {}}
    order: list[str] = []

    def claim(repo: str, number: int, token: str) -> None:
        order.append(f"claim:{number}")

    first = poll.process_issue(
        _issue(108),
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state=state,
        state_path=state_path,
        prompt_path=tmp_path / "missing.md",
        cmd=OK_CMD,
        claim=claim,
        comments=[],
    )
    assert first == "started"
    assert order == ["claim:108"]
    second = poll.process_issue(
        _issue(108),
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state=poll.load_state(state_path),
        state_path=state_path,
        prompt_path=tmp_path / "missing.md",
        cmd=OK_CMD,
        claim=claim,
        comments=[{"body": poll.CLAIM_MARKER}],
    )
    assert second == "skipped"
    assert order == ["claim:108"]


def test_claim_happens_before_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    def claim(repo: str, number: int, token: str) -> None:
        order.append("claim")

    def launch(issue_number: int, prompt: str, cmd: str | None = None) -> str:
        order.append("launch")
        return "cmd:ok"

    monkeypatch.setattr(poll, "launch_builder", launch)
    action = poll.process_issue(
        _issue(106),
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state={"started": {}},
        state_path=tmp_path / "state.json",
        prompt_path=tmp_path / "missing.md",
        cmd=OK_CMD,
        claim=claim,
        comments=[],
    )
    assert action == "started"
    assert order == ["claim", "launch"]


def test_poll_once_starts_only_one_issue(tmp_path: Path) -> None:
    claimed: list[int] = []

    def claim(repo: str, number: int, token: str) -> None:
        claimed.append(number)

    actions = poll.poll_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=tmp_path / "state.json",
        prompt_path=tmp_path / "missing.md",
        cmd=OK_CMD,
        list_issues=lambda *_: [_issue(106), _issue(107)],
        claim=claim,
    )
    assert actions == ["started"]
    assert claimed == [106]
    saved = poll.load_state(tmp_path / "state.json")
    assert "106" in saved["started"]
    assert "107" not in saved["started"]


def test_empty_repo_starts_nothing(tmp_path: Path) -> None:
    actions = poll.poll_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=tmp_path / "state.json",
        prompt_path=tmp_path / "missing.md",
        cmd=OK_CMD,
        list_issues=lambda *_: [],
    )
    assert actions == []
    assert not (tmp_path / "state.json").exists()


def test_process_issue_dry_run_does_not_write_state(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    action = poll.process_issue(
        _issue(108),
        repo="landjunge/gnom-hub-v1",
        token="",
        state={"started": {}},
        state_path=state_path,
        prompt_path=tmp_path / "missing.md",
        dry_run=True,
    )
    assert action == "dry-run"
    assert not state_path.exists()


def test_main_help_exits_zero() -> None:
    try:
        poll.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("expected SystemExit")
