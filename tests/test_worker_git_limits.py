"""Real Git pipes: bounded stdout+stderr, deadline and own-process cleanup only."""

import os
import subprocess
import time

import pytest

from gnom_hub import worker_stands
from gnom_hub.external_work import BindingError


def test_git_stdout_overflow_stops_at_combined_byte_allowance(tmp_path, monkeypatch):
    worker_stands.git(tmp_path, "init", "--quiet")
    for index in range(100):
        (tmp_path / (str(index) + "x" * 60)).write_text("synthetic")
    original_read = os.read
    sizes = []

    def measured(fd, maximum):
        raw = original_read(fd, maximum)
        sizes.append(len(raw))
        return raw

    monkeypatch.setattr(worker_stands.os, "read", measured)
    with pytest.raises(BindingError, match=r"^worker_git_output_limit$"):
        worker_stands.git(tmp_path, "status", "--porcelain", "--untracked-files=normal")
    assert sum(sizes) == worker_stands.GIT_OUTPUT_BYTES + 1


def test_git_stderr_overflow_is_bounded_and_sanitized(tmp_path, monkeypatch):
    original_read = os.read
    sizes = []

    def measured(fd, maximum):
        raw = original_read(fd, maximum)
        sizes.append(len(raw))
        return raw

    monkeypatch.setattr(worker_stands.os, "read", measured)
    # Real Git prints this failed filename on stderr, never on stdout.
    private = "SYNTHETIC_PRIVATE_MARKER" + "x" * 6000
    with pytest.raises(BindingError, match=r"^worker_git_output_limit$") as caught:
        worker_stands.git(tmp_path, "hash-object", private)
    assert private not in str(caught.value)
    assert sum(sizes) == worker_stands.GIT_OUTPUT_BYTES + 1


@pytest.mark.parametrize("deny_group", [False, True])
def test_git_timeout_kills_and_reaps_only_its_new_process_group(tmp_path, monkeypatch, deny_group):
    original_popen = subprocess.Popen
    original_killpg = os.killpg
    processes, signals = [], []

    def waiting_git(command, **kwargs):
        assert command == ["git", "-C", str(tmp_path), "hash-object", "--stdin"]
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["start_new_session"] is True
        # Test-only held pipe makes real Git wait indefinitely for input. The
        # production executable/arguments remain Git; no shell/interpreter stub.
        kwargs["stdin"] = subprocess.PIPE
        process = original_popen(command, **kwargs)
        processes.append(process)
        return process

    def own_signal(pid, sig):
        signals.append(pid)
        assert pid == processes[0].pid
        if deny_group:
            raise PermissionError("synthetic group denial")
        return original_killpg(pid, sig)

    monkeypatch.setattr(worker_stands.subprocess, "Popen", waiting_git)
    monkeypatch.setattr(worker_stands.os, "killpg", own_signal)
    monkeypatch.setattr(worker_stands, "GIT_TIMEOUT_S", 0.05)
    start = time.monotonic()
    with pytest.raises(BindingError, match=r"^worker_git_timeout$"):
        worker_stands.git(tmp_path, "hash-object", "--stdin")
    assert time.monotonic() - start < 1.5
    assert signals == [processes[0].pid]
    assert processes[0].returncode is not None
    assert all(
        stream.closed for stream in (processes[0].stdin, processes[0].stdout, processes[0].stderr)
    )


def test_git_small_success_and_failure_keep_exact_sanitized_contract(tmp_path):
    assert worker_stands.git(tmp_path, "--version").startswith("git version ")
    with pytest.raises(BindingError, match=r"^worker_git_unavailable$"):
        worker_stands.git(tmp_path, "hash-object", "SYNTHETIC_MISSING_FILE")
