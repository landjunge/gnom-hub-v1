"""Plugin: extended allowlisted shell (God-Mode for real exec)."""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

_ALLOW = frozenset(
    {
        "ls",
        "pwd",
        "date",
        "uname",
        "whoami",
        "echo",
        "cat",
        "head",
        "tail",
        "wc",
        "df",
        "du",
        "which",
        "python3",
        "python",
        "git",
        "open",
    }
)
_SAFE_ARG = re.compile(r"^[A-Za-z0-9_./@%+=:,\-?&#~*]+$")


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


def shell_safe_allowlist() -> dict[str, Any]:
    return {"ok": True, "allow": sorted(_ALLOW), "god_mode": _god()}


def shell_safe(cmd: str = "") -> dict[str, Any]:
    raw = (cmd or "").strip()
    if not raw:
        return {"ok": False, "error": "empty cmd"}
    if any(ch in raw for ch in ("|", ";", "&", ">", "<", "`", "$", "\n", "\\")):
        return {"ok": False, "error": "shell metacharacters blocked"}
    try:
        parts = shlex.split(raw)
    except ValueError as exc:
        return {"ok": False, "error": f"parse: {exc}"}
    if not parts:
        return {"ok": False, "error": "empty after parse"}
    binary = parts[0]
    if "/" in binary or binary not in _ALLOW:
        return {"ok": False, "error": f"not allowlisted: {binary}", "allow": sorted(_ALLOW)}
    if binary in ("python", "python3") and parts[1:] not in (["-V"], ["--version"]):
        return {"ok": False, "error": "python restricted to -V / --version"}
    if binary == "git" and parts[1:2] not in (  # noqa: SIM102
        ["status"],
        ["diff"],
        ["log"],
        ["branch"],
        ["rev-parse"],
    ):
        # read-only git via shell_safe; commits via git_ops + God-Mode
        if not parts[1:2] or parts[1] not in (
            "status",
            "diff",
            "log",
            "branch",
            "rev-parse",
            "show",
        ):
            return {
                "ok": False,
                "error": "git via shell_safe is read-only (status/diff/log/branch)",
            }
    for arg in parts[1:]:
        if not _SAFE_ARG.match(arg):
            return {"ok": False, "error": f"unsafe arg: {arg!r}"}

    if not _god():
        return {
            "ok": True,
            "dry_run": True,
            "detail": f"dry-run shell_safe: {raw!r} — enable God-Mode to execute",
            "cmd": raw,
        }

    try:
        proc = subprocess.run(
            parts,
            cwd=str(_root()),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "cmd": raw}
    return {
        "ok": proc.returncode == 0,
        "dry_run": False,
        "exit": proc.returncode,
        "stdout": (proc.stdout or "")[:4000],
        "stderr": (proc.stderr or "")[:1000],
        "cmd": raw,
        "cwd": str(_root()),
    }
