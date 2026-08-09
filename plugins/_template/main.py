"""Template plugin — rename folder (drop leading _) and set plugin.json id."""

from __future__ import annotations

from gnom_hub.plugins.sdk import fail, ok


def on_load(info: dict) -> None:
    # optional: warm caches, check deps
    _ = info


def run(input: str = "") -> dict:  # noqa: A002 — schema field name
    if not str(input).strip():
        return fail("input is required")
    return ok(result=str(input), plugin="my_plugin")
