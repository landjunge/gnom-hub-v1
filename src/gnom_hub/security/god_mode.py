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
    audit: list[dict] = field(default_factory=list)

    def enable(self, reason: str = "user") -> None:
        self.enabled = True
        self.enabled_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.reason = reason
        self._log("enable", reason)

    def disable(self, reason: str = "user") -> None:
        self.enabled = False
        self.enabled_at = None
        self.reason = ""
        self._log("disable", reason)

    def allow_path(self, path: str) -> bool:
        """In normal mode only relative workspace/data; god mode allows absolute."""
        p = path.replace("\\", "/")
        if self.enabled:
            return True
        # safe defaults
        if p.startswith(("data/", "gnom_workspace/")) or "/data/" in p:
            return True
        if ".." in p.split("/"):
            return False
        return not p.startswith("/")

    def snapshot(self) -> dict:
        return {
            "enabled": self.enabled,
            "enabled_at": self.enabled_at,
            "reason": self.reason,
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
    gm = GodMode()
    if os.getenv("GNOM_GOD_MODE_AUTO", "").strip().lower() in ("1", "true", "yes"):
        gm.enable("env:GNOM_GOD_MODE_AUTO")
    return gm
