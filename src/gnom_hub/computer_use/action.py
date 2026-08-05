"""Action executor — blocked unless God-Mode; shell uses strict allowlist."""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any

# Only these bare commands may run under God-Mode (no pipes/redirects).
_SHELL_ALLOW = frozenset(
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
    }
)
_SAFE_ARG = re.compile(r"^[A-Za-z0-9_./@%+=:,-]+$")


@dataclass
class ActionResult:
    ok: bool
    dry_run: bool
    detail: str
    stdout: str = ""
    stderr: str = ""


class ActionModule:
    def __init__(self, *, god_mode_enabled: bool = False) -> None:
        self.god_mode_enabled = god_mode_enabled

    def set_god_mode(self, enabled: bool) -> None:
        self.god_mode_enabled = enabled

    def click(self, x: int, y: int) -> ActionResult:
        if not self.god_mode_enabled:
            return ActionResult(True, True, f"dry-run click ({x},{y}) — enable God-Mode to execute")
        try:
            import pyautogui  # type: ignore

            pyautogui.click(x, y)
            return ActionResult(True, False, f"clicked ({x},{y})")
        except Exception as exc:  # noqa: BLE001
            return ActionResult(False, False, f"click failed: {exc}")

    def type_text(self, text: str) -> ActionResult:
        if not self.god_mode_enabled:
            return ActionResult(True, True, f"dry-run type {text!r} — enable God-Mode to execute")
        try:
            import pyautogui  # type: ignore

            pyautogui.typewrite(text, interval=0.02)
            return ActionResult(True, False, "typed")
        except Exception as exc:  # noqa: BLE001
            return ActionResult(False, False, f"type failed: {exc}")

    def run_shell(self, cmd: str) -> ActionResult:
        raw = (cmd or "").strip()
        if not raw:
            return ActionResult(False, True, "empty command")
        if not self.god_mode_enabled:
            return ActionResult(True, True, f"dry-run shell: {raw!r}")

        # Reject shell metacharacters
        if any(ch in raw for ch in ("|", ";", "&", ">", "<", "`", "$", "\n", "\\")):
            return ActionResult(False, False, "shell metacharacters blocked")

        try:
            parts = shlex.split(raw)
        except ValueError as exc:
            return ActionResult(False, False, f"parse error: {exc}")
        if not parts:
            return ActionResult(False, False, "empty after parse")

        binary = parts[0]
        if "/" in binary or binary not in _SHELL_ALLOW:
            return ActionResult(
                False,
                False,
                f"command not allowlisted: {binary!r} (allowed: {sorted(_SHELL_ALLOW)})",
            )
        for arg in parts[1:]:
            if not _SAFE_ARG.match(arg):
                return ActionResult(False, False, f"unsafe argument blocked: {arg!r}")

        try:
            proc = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            return ActionResult(
                ok=proc.returncode == 0,
                dry_run=False,
                detail=f"exit={proc.returncode}",
                stdout=(proc.stdout or "")[:4000],
                stderr=(proc.stderr or "")[:1000],
            )
        except Exception as exc:  # noqa: BLE001
            return ActionResult(False, False, f"shell failed: {exc}")

    def snapshot(self) -> dict[str, Any]:
        return {
            "god_mode": self.god_mode_enabled,
            "shell_allow": sorted(_SHELL_ALLOW),
        }
