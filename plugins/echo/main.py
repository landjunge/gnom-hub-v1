"""Demo plugin tool — uses optional gnom_hub.plugins.sdk helpers."""

from __future__ import annotations

from typing import Any

from gnom_hub.plugins.sdk import fail, ok

_LOADED = {"n": 0}


def on_load(info: dict[str, Any]) -> None:
    """Optional lifecycle hook called after tools register."""
    _LOADED["n"] += 1
    _LOADED["tools"] = list(info.get("tools") or [])


def run(text: str = "") -> dict[str, Any]:
    if text is None or str(text).strip() == "":
        return fail("text is required")
    return ok(echo=str(text), plugin="echo", loads=_LOADED["n"])
