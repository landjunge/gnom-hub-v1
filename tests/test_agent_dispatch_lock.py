"""Dispatcher D1 — one instance per tick, atomic RUNNING claim."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from test_agent_dispatch import NOW, ROOT, _issue, _seed_tested, _snap, ad

PY = sys.executable
SCRIPT = ROOT / "scripts" / "agent_dispatch.py"


def _builder_snap():
    return _snap(teilaufgaben=[_issue(107)], pulls=[], baseline_sha="base-sha")


def _hold_lock(lock: Path, ready: Path, hold_sec: float = 2.0) -> subprocess.Popen:
    return subprocess.Popen(
        [
            PY,
            "-c",
            "import importlib.util, sys, time\n"
            "from pathlib import Path\n"
            f"script = Path({str(SCRIPT)!r})\n"
            f"lock = Path({str(lock)!r})\n"
            f"ready = Path({str(ready)!r})\n"
            "spec = importlib.util.spec_from_file_location('gnom_agent_dispatch', script)\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "assert spec and spec.loader\n"
            "sys.modules['gnom_agent_dispatch'] = mod\n"
            "spec.loader.exec_module(mod)\n"
            "fd = mod.acquire_instance_lock(lock)\n"
            "assert fd is not None\n"
            "ready.write_text('1', encoding='utf-8')\n"
            f"time.sleep({hold_sec!r})\n"
            "mod.release_instance_lock(fd)\n",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_ready(path: Path, proc: subprocess.Popen, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not path.is_file():
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    err = ""
    if proc.poll() is not None and proc.stderr is not None:
        err = proc.stderr.read()
    assert path.is_file(), err or f"{path.name} missing before lock holder exited"


def test_priority_unchanged() -> None:
    assert ad.PRIORITY == (
        "review-fixes",
        "reviewer",
        "test-agent",
        "builder",
        "planer",
        "koordinator",
    )


def _assert_lock_free(path: Path) -> None:
    fd = ad.acquire_instance_lock(path)
    assert fd is not None
    ad.release_instance_lock(fd)


def _dispatch(state_path: Path, launch, **kwargs):
    return ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=state_path,
        agents_dir=ROOT / "agents",
        snapshot=_builder_snap(),
        launch=launch,
        now=NOW,
        **kwargs,
    )


def test_default_lock_path_sits_beside_state(tmp_path: Path) -> None:
    state = tmp_path / "agent_dispatch_state.json"
    assert ad.default_lock_path(state) == tmp_path / "agent_dispatch.lock"
    assert ad.DEFAULT_LOCK.name == "agent_dispatch.lock"


def test_load_state_keeps_running_claim(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    ad.save_state(
        path,
        {
            "started": {},
            "last_test_sha": "base-sha",
            "running": {"key": "builder:issue:107", "role": "builder"},
        },
    )
    loaded = ad.load_state(path)
    assert loaded["running"]["key"] == "builder:issue:107"
    assert loaded["running"]["role"] == "builder"


def test_acquire_instance_lock_excludes_second_process(tmp_path: Path) -> None:
    lock = tmp_path / "agent_dispatch.lock"
    ready = tmp_path / "held"
    holder = _hold_lock(lock, ready, hold_sec=2.0)
    try:
        _wait_ready(ready, holder)
        assert ad.acquire_instance_lock(lock) is None
    finally:
        holder.wait(timeout=10)
    assert holder.returncode == 0, holder.stderr.read() if holder.stderr else ""
    fd = ad.acquire_instance_lock(lock)
    assert fd is not None
    ad.release_instance_lock(fd)


def test_dispatch_once_busy_when_lock_held(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    lock = tmp_path / "agent_dispatch.lock"
    ready = tmp_path / "held"
    launched: list[str] = []
    _seed_tested(state_path)
    holder = _hold_lock(lock, ready, hold_sec=3.0)
    try:
        _wait_ready(ready, holder)
        action = ad.dispatch_once(
            repo="landjunge/gnom-hub-v1",
            token="tok",
            state_path=state_path,
            agents_dir=ROOT / "agents",
            snapshot=_builder_snap(),
            launch=lambda *_a, **_k: launched.append("x") or "ok",
            lock_path=lock,
            now=NOW,
        )
        assert action == "busy"
        assert launched == []
        saved = ad.load_state(state_path)
        assert saved["started"] == {}
        assert "running" not in saved
    finally:
        holder.wait(timeout=10)
    assert holder.returncode == 0, holder.stderr.read() if holder.stderr else ""


def test_running_claim_released_on_launch_failed(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _seed_tested(state_path)
    during: dict = {}
    calls = {"n": 0}

    def boom_then_ok(role: str, prompt: str, env: dict) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            during["running"] = ad.load_state(state_path).get("running")
            raise RuntimeError("no-grok")
        return "ok"

    action = _dispatch(state_path, boom_then_ok)
    assert action == "launch-failed"
    claim = during["running"]
    assert isinstance(claim, dict)
    assert claim["role"] == "builder"
    assert "issue:107" in str(claim.get("key") or "")
    saved = ad.load_state(state_path)
    assert "running" not in saved
    assert saved["started"] == {}
    _assert_lock_free(ad.default_lock_path(state_path))
    again = _dispatch(state_path, boom_then_ok)
    assert again == "started"
    assert calls["n"] == 2
    saved = ad.load_state(state_path)
    assert "running" not in saved
    assert saved["started"]


def test_running_claim_released_on_tick_done(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _seed_tested(state_path)
    during: dict = {}

    def ok(role: str, prompt: str, env: dict) -> str:
        during["running"] = ad.load_state(state_path).get("running")
        return "ok"

    action = _dispatch(state_path, ok)
    assert action == "started"
    claim = during["running"]
    assert isinstance(claim, dict)
    assert claim["role"] == "builder"
    saved = ad.load_state(state_path)
    assert "running" not in saved
    assert saved["started"]
    _assert_lock_free(ad.default_lock_path(state_path))
    again = _dispatch(state_path, lambda *_a, **_k: "nope")
    assert again == "idle"


def test_running_claim_released_on_unexpected_error(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _seed_tested(state_path)
    calls = {"n": 0}

    def boom_then_ok(role: str, prompt: str, env: dict) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("boom")
        return "ok"

    try:
        _dispatch(state_path, boom_then_ok)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    saved = ad.load_state(state_path)
    assert "running" not in saved
    assert saved["started"] == {}
    _assert_lock_free(ad.default_lock_path(state_path))
    again = _dispatch(state_path, boom_then_ok)
    assert again == "started"
    assert calls["n"] == 2
    assert "running" not in ad.load_state(state_path)


def test_stale_running_claim_dropped_before_pick(tmp_path: Path, capsys) -> None:
    state_path = tmp_path / "state.json"
    stale_key = "builder:repo:landjunge/gnom-hub-v1:issue:99:open-teilaufgabe"
    ad.save_state(
        state_path,
        {
            "started": {},
            "last_test_sha": "base-sha",
            "running": {
                "key": stale_key,
                "role": "builder",
                "reason": "open-teilaufgabe",
                "at": "2026-09-20T14:00:00Z",
                "pid": 1,
            },
        },
    )
    seen: dict = {}

    def launch(role: str, prompt: str, env: dict) -> str:
        seen["running"] = ad.load_state(state_path).get("running")
        return "ok"

    action = _dispatch(state_path, launch)
    assert action == "started"
    claim = seen["running"]
    assert isinstance(claim, dict)
    assert claim.get("key") != stale_key
    assert "issue:107" in str(claim.get("key") or "")
    assert "stale-claim" in capsys.readouterr().out
    saved = ad.load_state(state_path)
    assert "running" not in saved


def test_two_parallel_dispatch_only_one_launches(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    lock_path = tmp_path / "agent_dispatch.lock"
    launched_path = tmp_path / "launched.txt"
    ready_path = tmp_path / "ready"
    result_a = tmp_path / "result_a.txt"
    result_b = tmp_path / "result_b.txt"
    err_a = tmp_path / "err_a.txt"
    err_b = tmp_path / "err_b.txt"
    child = tmp_path / "tick.py"
    _seed_tested(state_path)
    child.write_text(
        "from __future__ import annotations\n"
        "import importlib.util\n"
        "import sys\n"
        "import time\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n"
        "\n"
        "script = Path(sys.argv[1])\n"
        "state_path = Path(sys.argv[2])\n"
        "lock_path = Path(sys.argv[3])\n"
        "result_path = Path(sys.argv[4])\n"
        "launched_path = Path(sys.argv[5])\n"
        "ready_path = Path(sys.argv[6])\n"
        "hold_sec = float(sys.argv[7])\n"
        "spec = importlib.util.spec_from_file_location('gnom_agent_dispatch', script)\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "assert spec and spec.loader\n"
        "sys.modules['gnom_agent_dispatch'] = mod\n"
        "spec.loader.exec_module(mod)\n"
        "now = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)\n"
        "snap = mod.Snapshot(\n"
        "    teilaufgaben=[{\n"
        "        'number': 107,\n"
        "        'state': 'open',\n"
        "        'title': 'T107',\n"
        "        'labels': [{'name': 'teilaufgabe'}],\n"
        "        'updated_at': '2026-09-20T15:54:00Z',\n"
        "    }],\n"
        "    pulls=[],\n"
        "    reviews={},\n"
        "    haupt={'number': 105, 'state': 'open'},\n"
        "    baseline_sha='base-sha',\n"
        "    now=now,\n"
        ")\n"
        "\n"
        "def launch(role: str, prompt: str, env: dict) -> str:\n"
        "    ready_path.write_text('1', encoding='utf-8')\n"
        "    with launched_path.open('a', encoding='utf-8') as fh:\n"
        "        fh.write('1\\n')\n"
        "        fh.flush()\n"
        "    time.sleep(hold_sec)\n"
        "    return 'ok'\n"
        "\n"
        "action = mod.dispatch_once(\n"
        "    repo='landjunge/gnom-hub-v1',\n"
        "    token='tok',\n"
        "    state_path=state_path,\n"
        "    agents_dir=script.resolve().parent.parent / 'agents',\n"
        "    snapshot=snap,\n"
        "    launch=launch,\n"
        "    lock_path=lock_path,\n"
        "    now=now,\n"
        ")\n"
        "result_path.write_text(action, encoding='utf-8')\n",
        encoding="utf-8",
    )

    def start(result: Path, err: Path) -> subprocess.Popen:
        return subprocess.Popen(
            [
                PY,
                str(child),
                str(SCRIPT),
                str(state_path),
                str(lock_path),
                str(result),
                str(launched_path),
                str(ready_path),
                "2.0",
            ],
            stdout=subprocess.DEVNULL,
            stderr=err.open("w", encoding="utf-8"),
        )

    first = start(result_a, err_a)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not ready_path.is_file():
        time.sleep(0.05)
    assert ready_path.is_file(), err_a.read_text(encoding="utf-8")
    second = start(result_b, err_b)
    assert first.wait(timeout=15) == 0, err_a.read_text(encoding="utf-8")
    assert second.wait(timeout=15) == 0, err_b.read_text(encoding="utf-8")
    actions = {result_a.read_text(encoding="utf-8"), result_b.read_text(encoding="utf-8")}
    assert actions == {"started", "busy"}
    assert launched_path.read_text(encoding="utf-8").splitlines() == ["1"]
    saved = ad.load_state(state_path)
    assert "running" not in saved
    assert saved["started"]


def _live_claim() -> dict:
    return {
        "key": "builder:repo:landjunge/gnom-hub-v1:issue:99:open-teilaufgabe",
        "role": "builder",
        "reason": "open-teilaufgabe",
        "at": "2026-09-20T14:00:00Z",
        "pid": 9,
    }


def test_load_state_drops_empty_or_nondict_running(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    for running in ({}, "builder", [], None):
        path.write_text(
            json.dumps({"started": {}, "last_test_sha": "base-sha", "running": running}) + "\n",
            encoding="utf-8",
        )
        loaded = ad.load_state(path)
        assert "running" not in loaded
        assert loaded["last_test_sha"] == "base-sha"


def test_lock_fd_closes_on_exec(tmp_path: Path) -> None:
    lock = tmp_path / "agent_dispatch.lock"
    fd = ad.acquire_instance_lock(lock)
    assert fd is not None
    try:
        flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        assert flags & fcntl.FD_CLOEXEC
        assert lock.read_text(encoding="ascii").strip() == str(os.getpid())
    finally:
        ad.release_instance_lock(fd)
    _assert_lock_free(lock)


def test_dry_run_does_not_create_lock_or_running(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    lock = tmp_path / "agent_dispatch.lock"
    _seed_tested(state_path)
    launched: list[str] = []
    action = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=state_path,
        agents_dir=ROOT / "agents",
        dry_run=True,
        snapshot=_builder_snap(),
        launch=lambda *_a, **_k: launched.append("x") or "ok",
        lock_path=lock,
        now=NOW,
    )
    assert action == "dry-run"
    assert launched == []
    assert not lock.exists()
    saved = ad.load_state(state_path)
    assert "running" not in saved
    assert saved["started"] == {}


def test_dry_run_proceeds_while_instance_lock_held(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    lock = tmp_path / "agent_dispatch.lock"
    ready = tmp_path / "held"
    live = _live_claim()
    ad.save_state(
        state_path,
        {"started": {}, "last_test_sha": "base-sha", "running": live},
    )
    launched: list[str] = []
    holder = _hold_lock(lock, ready, hold_sec=3.0)
    try:
        _wait_ready(ready, holder)
        action = ad.dispatch_once(
            repo="landjunge/gnom-hub-v1",
            token="tok",
            state_path=state_path,
            agents_dir=ROOT / "agents",
            dry_run=True,
            snapshot=_builder_snap(),
            launch=lambda *_a, **_k: launched.append("x") or "ok",
            lock_path=lock,
            now=NOW,
        )
        assert action == "dry-run"
        assert launched == []
        assert ad.acquire_instance_lock(lock) is None
        saved = ad.load_state(state_path)
        assert saved["running"] == live
        assert saved["started"] == {}
    finally:
        holder.wait(timeout=10)
    assert holder.returncode == 0, holder.stderr.read() if holder.stderr else ""


def test_busy_keeps_live_claim_and_skips_github(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    lock = tmp_path / "agent_dispatch.lock"
    ready = tmp_path / "held"
    live = _live_claim()
    ad.save_state(
        state_path,
        {"started": {}, "last_test_sha": "base-sha", "running": live},
    )
    calls: list[str] = []
    launched: list[str] = []

    def github(method: str, url: str, token: str, body: dict | None = None) -> list:
        calls.append(url)
        return []

    holder = _hold_lock(lock, ready, hold_sec=3.0)
    try:
        _wait_ready(ready, holder)
        action = ad.dispatch_once(
            repo="landjunge/gnom-hub-v1",
            token="tok",
            state_path=state_path,
            agents_dir=ROOT / "agents",
            snapshot=None,
            launch=lambda *_a, **_k: launched.append("x") or "ok",
            github=github,
            lock_path=lock,
            now=NOW,
        )
        assert action == "busy"
        assert calls == []
        assert launched == []
        saved = ad.load_state(state_path)
        assert saved["running"] == live
        assert saved["started"] == {}
    finally:
        holder.wait(timeout=10)
    assert holder.returncode == 0, holder.stderr.read() if holder.stderr else ""


def test_idle_tick_drops_stale_running_claim(tmp_path: Path, capsys) -> None:
    state_path = tmp_path / "state.json"
    live = _live_claim()
    ad.save_state(
        state_path,
        {"started": {}, "last_test_sha": "base-sha", "running": live},
    )
    launched: list[str] = []
    snap = _snap(
        teilaufgaben=[],
        pulls=[],
        baseline_sha="base-sha",
        haupt={"number": 105, "state": "closed"},
    )
    action = ad.dispatch_once(
        repo="landjunge/gnom-hub-v1",
        token="tok",
        state_path=state_path,
        agents_dir=ROOT / "agents",
        snapshot=snap,
        launch=lambda *_a, **_k: launched.append("x") or "ok",
        now=NOW,
    )
    assert action == "idle"
    assert launched == []
    out = capsys.readouterr().out
    assert "stale-claim" in out
    assert live["key"] in out
    saved = ad.load_state(state_path)
    assert "running" not in saved
    assert saved["started"] == {}
    _assert_lock_free(ad.default_lock_path(state_path))


def test_running_claim_records_reason_at_and_pid(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _seed_tested(state_path)
    during: dict = {}

    def ok(role: str, prompt: str, env: dict) -> str:
        during["running"] = ad.load_state(state_path).get("running")
        return "ok"

    action = _dispatch(state_path, ok)
    assert action == "started"
    claim = during["running"]
    assert isinstance(claim, dict)
    assert claim["role"] == "builder"
    assert claim["reason"] == "open-teilaufgabe"
    assert claim["at"] == ad.utc_stamp(NOW)
    assert claim["pid"] == os.getpid()
    assert "issue:107" in claim["key"]
    assert str(claim["key"]).endswith(":open-teilaufgabe")
    saved = ad.load_state(state_path)
    assert "running" not in saved
    assert saved["started"]


def test_unexpected_error_stored_claim_before_raise(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _seed_tested(state_path)
    during: dict = {}

    def boom(role: str, prompt: str, env: dict) -> str:
        during["running"] = ad.load_state(state_path).get("running")
        raise ValueError("boom")

    try:
        _dispatch(state_path, boom)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    claim = during["running"]
    assert isinstance(claim, dict)
    assert claim["role"] == "builder"
    assert claim["reason"] == "open-teilaufgabe"
    assert "issue:107" in str(claim.get("key") or "")
    saved = ad.load_state(state_path)
    assert "running" not in saved
    assert saved["started"] == {}
    _assert_lock_free(ad.default_lock_path(state_path))


def test_disabled_does_not_take_instance_lock(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GNOM_AGENT_DISPATCH", "0")
    state_path = tmp_path / "state.json"
    lock = tmp_path / "agent_dispatch.lock"
    ready = tmp_path / "held"
    holder = _hold_lock(lock, ready, hold_sec=3.0)
    try:
        _wait_ready(ready, holder)
        action = ad.dispatch_once(
            repo="landjunge/gnom-hub-v1",
            token="tok",
            state_path=state_path,
            agents_dir=ROOT / "agents",
            snapshot=_builder_snap(),
            launch=lambda *_a, **_k: "ok",
            lock_path=lock,
            now=NOW,
        )
        assert action == "disabled"
        assert not state_path.is_file()
        assert ad.acquire_instance_lock(lock) is None
    finally:
        holder.wait(timeout=10)
    assert holder.returncode == 0, holder.stderr.read() if holder.stderr else ""


def test_no_token_does_not_take_instance_lock(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    lock = tmp_path / "agent_dispatch.lock"
    ready = tmp_path / "held"
    holder = _hold_lock(lock, ready, hold_sec=3.0)
    try:
        _wait_ready(ready, holder)
        action = ad.dispatch_once(
            repo="landjunge/gnom-hub-v1",
            token="",
            state_path=state_path,
            agents_dir=ROOT / "agents",
            snapshot=_builder_snap(),
            launch=lambda *_a, **_k: "ok",
            lock_path=lock,
            now=NOW,
        )
        assert action == "no-token"
        assert not state_path.is_file()
        assert ad.acquire_instance_lock(lock) is None
    finally:
        holder.wait(timeout=10)
    assert holder.returncode == 0, holder.stderr.read() if holder.stderr else ""
