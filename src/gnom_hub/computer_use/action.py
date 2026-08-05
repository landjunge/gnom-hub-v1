"""Action executor — blocked unless God-Mode; otherwise dry-run only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ActionResult:
    ok: bool
    dry_run: bool
    detail: str


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
        # Never auto-run shell even in god mode without explicit API — still dry-run report
        if not self.god_mode_enabled:
            return ActionResult(True, True, f"dry-run shell: {cmd!r}")
        return ActionResult(
            True,
            True,
            f"god-mode shell still dry-run in v2 lite (safety): {cmd!r}",
        )

    def snapshot(self) -> dict[str, Any]:
        return {"god_mode": self.god_mode_enabled}
