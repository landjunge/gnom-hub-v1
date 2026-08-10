"""Plugin: git status/diff/commit inside hub project root only."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _root() -> Path:
    try:
        from gnom_hub.config.paths import project_root

        return project_root().resolve()
    except Exception:  # noqa: BLE001
        return Path.cwd().resolve()


def _god() -> bool:
    try:
        from gnom_hub.hub import get_hub

        return bool(get_hub().god_mode.enabled)
    except Exception:  # noqa: BLE001
        return False


def _run(args: list[str], timeout: float = 30) -> dict[str, Any]:
    root = _root()
    try:
        proc = subprocess.run(
            args,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "cwd": str(root)}
    return {
        "ok": proc.returncode == 0,
        "exit": proc.returncode,
        "stdout": (proc.stdout or "")[:8000],
        "stderr": (proc.stderr or "")[:2000],
        "cwd": str(root),
        "cmd": " ".join(args),
    }


def git_status() -> dict[str, Any]:
    return _run(["git", "status", "--short", "-b"])


def git_diff(stat: bool = True) -> dict[str, Any]:
    if stat:
        return _run(["git", "diff", "--stat"])
    return _run(["git", "diff", "--", ".", ":(exclude)*.pyc", ":(exclude)__pycache__"])


def git_commit(message: str = "") -> dict[str, Any]:
    msg = (message or "").strip()
    if not msg:
        return {"ok": False, "error": "message required"}
    if not _god():
        return {
            "ok": False,
            "blocked": True,
            "dry_run": True,
            "error": "git_commit requires God-Mode",
            "would": f"git add -A && git commit -m {msg!r}",
        }
    # safety: no force, no push
    add = _run(["git", "add", "-A"])
    if not add.get("ok") and add.get("exit") not in (0, None):
        return {"ok": False, "step": "add", **add}
    commit = _run(["git", "commit", "-m", msg[:200]])
    return {"ok": bool(commit.get("ok")), "add": add, "commit": commit}
