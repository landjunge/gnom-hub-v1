"""Polling daemon for open teilaufgabe issues — no live GitHub."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "poll_teilaufgaben.py"


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


def test_interval_default_is_between_30_and_60():
    assert 30 <= poll.DEFAULT_INTERVAL <= 60


def test_already_started_on_in_bearbeitung():
    issue = _issue(106, labels=["teilaufgabe", "in-bearbeitung"])
    assert poll.already_started(issue, {"started": {}}) is True


def test_already_started_on_state_file():
    issue = _issue(108)
    state = {"started": {"108": {"at": "2026-09-20T12:00:00Z"}}}
    assert poll.already_started(issue, state) is True
    assert poll.already_started(_issue(107), state) is False


def test_already_started_on_claim_comment():
    issue = _issue(108)
    comments = [{"body": poll.CLAIM_MARKER + "\nBuilder-Poll startet Issue #108."}]
    assert poll.already_started(issue, {"started": {}}, comments) is True


def test_builder_prompt_includes_role_and_issue(tmp_path: Path):
    role = tmp_path / "builder.md"
    role.write_text("Du bist der Builder-Agent.\n", encoding="utf-8")
    text = poll.builder_prompt(108, role)
    assert "Builder-Agent" in text
    assert "#108" in text
    assert "baseline" in text


def test_process_issue_dry_run_does_not_write_state(tmp_path: Path):
    state_path = tmp_path / "state.json"
    action = poll.process_issue(
        _issue(108, title="poll"),
        repo="landjunge/gnom-hub-v1",
        token="",
        state={"started": {}},
        state_path=state_path,
        launch_dir=tmp_path / "launch",
        prompt_path=tmp_path / "missing.md",
        dry_run=True,
    )
    assert action == "dry-run"
    assert not state_path.exists()


def test_process_issue_persists_and_blocks_second_start(tmp_path: Path):
    state_path = tmp_path / "state.json"
    state: dict = {"started": {}}
    first = poll.process_issue(
        _issue(108, title="poll"),
        repo="landjunge/gnom-hub-v1",
        token="",
        state=state,
        state_path=state_path,
        launch_dir=tmp_path / "launch",
        prompt_path=tmp_path / "missing.md",
        dry_run=False,
    )
    assert first == "started"
    assert state_path.is_file()
    queued = tmp_path / "launch" / "108.txt"
    assert queued.is_file()
    assert "#108" in queued.read_text(encoding="utf-8")
    second = poll.process_issue(
        _issue(108, title="poll"),
        repo="landjunge/gnom-hub-v1",
        token="",
        state=poll.load_state(state_path),
        state_path=state_path,
        launch_dir=tmp_path / "launch",
        prompt_path=tmp_path / "missing.md",
        dry_run=False,
    )
    assert second == "skipped"


def test_main_help_exits_zero():
    try:
        poll.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("expected SystemExit")
