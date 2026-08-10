"""Action executor — blocked unless God-Mode; shell uses strict allowlist + path jail."""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
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
        # macOS: open URLs / apps for live browser navigation (God-Mode only)
        "open",
        # agent diagnostics (no free shell — still allowlisted only)
        "which",
        "python3",
        "python",
    }
)
# Commands whose non-flag args are treated as filesystem paths (M6 jail)
_PATH_CMDS = frozenset({"cat", "head", "tail", "wc", "du", "ls"})
# Allow URL args for `open https://…` (no shell metacharacters)
_SAFE_ARG = re.compile(r"^[A-Za-z0-9_./@%+=:,\-?&#~]+$")


@dataclass
class ActionResult:
    ok: bool
    dry_run: bool
    detail: str
    stdout: str = ""
    stderr: str = ""


class ActionModule:
    def __init__(
        self,
        *,
        god_mode_enabled: bool = False,
        root: Path | None = None,
    ) -> None:
        self.god_mode_enabled = god_mode_enabled
        self.root = Path(root) if root is not None else Path.cwd()

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

    def _path_in_jail(self, arg: str) -> bool:
        """True if path stays under project root / data / gnom_workspace."""
        raw = (arg or "").strip()
        if not raw or raw.startswith("-"):
            return True  # flags / empty
        # Reject traversal tokens early
        if ".." in Path(raw).parts or ".." in raw.replace("\\", "/").split("/"):
            return False
        root = self.root.resolve()
        candidates = [
            root,
            (root / "data").resolve(),
            (root / "gnom_workspace").resolve(),
        ]
        try:
            p = Path(raw)
            resolved = p.resolve() if p.is_absolute() else (root / raw).resolve()
        except (OSError, RuntimeError, ValueError):
            return False
        for base in candidates:
            try:
                resolved.relative_to(base)
                return True
            except ValueError:
                continue
        return False

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
        # python/python3: version only (installs go through tool_ensure, not free -c)
        if binary in ("python", "python3") and parts[1:] not in (["-V"], ["--version"]):
            return ActionResult(
                False,
                False,
                "python restricted to -V / --version (use tool_ensure for packages)",
            )
        for arg in parts[1:]:
            if not _SAFE_ARG.match(arg):
                return ActionResult(False, False, f"unsafe argument blocked: {arg!r}")
            # M6: path jail for file-reading commands
            if binary in _PATH_CMDS and not arg.startswith("-") and not self._path_in_jail(arg):
                return ActionResult(
                    False,
                    False,
                    f"path outside workspace jail: {arg!r}",
                )

        try:
            proc = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                cwd=str(self.root),
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
            "path_jail_root": str(self.root),
        }
