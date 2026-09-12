"""God-Mode: explicit elevated rights flag (off by default)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class GodMode:
    """
    When enabled, agents may request broader FS/shell paths.
    Must be turned on consciously (API or GNOM_GOD_MODE=1 at start still starts OFF
    unless GNOM_GOD_MODE_AUTO=1).
    """

    enabled: bool = False
    enabled_at: str | None = None
    reason: str = ""
    assignment_id: str = ""
    audit: list[dict] = field(default_factory=list)

    def enable(self, reason: str = "user", assignment_id: str = "") -> None:
        why = str(reason or "").strip() or "user"
        if why != "user" and not why.startswith("user:") and why != "api":
            raise PermissionError("God-Mode can only be enabled by the user switch")
        self.enabled = True
        self.enabled_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.reason = why
        self.assignment_id = str(assignment_id or "").strip()
        self._log("enable", why)

    def disable(self, reason: str = "user") -> None:
        self.enabled = False
        self.enabled_at = None
        self.reason = ""
        self.assignment_id = ""
        self._log("disable", reason)

    def allow_path(self, path: str) -> bool:
        """In normal mode only relative workspace/data; god mode allows absolute."""
        p = path.replace("\\", "/")
        # M7: always reject traversal before any allowlist prefix match
        if ".." in p.split("/"):
            return False
        if self.enabled:
            return True
        # safe defaults (no .. left)
        if p.startswith(("data/", "gnom_workspace/")) or "/data/" in p:
            return True
        return not p.startswith("/")

    def snapshot(self) -> dict:
        return {
            "enabled": self.enabled,
            "enabled_at": self.enabled_at,
            "reason": self.reason,
            "assignment_id": self.assignment_id,
            "audit_tail": self.audit[-10:],
        }

    def _log(self, action: str, reason: str) -> None:
        self.audit.append(
            {
                "action": action,
                "reason": reason,
                "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            }
        )
        if len(self.audit) > 100:
            self.audit = self.audit[-100:]


def god_mode_from_env() -> GodMode:
    """Always start off. Env cannot arm God-Mode (user switch only)."""
    _ = os.getenv("GNOM_GOD_MODE_AUTO", "")
    return GodMode()
