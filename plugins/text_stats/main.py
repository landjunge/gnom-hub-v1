"""text_stats plugin — word/line/char counts."""

from __future__ import annotations

from gnom_hub.plugins.sdk import ok


def run(text: str = "") -> dict:
    s = str(text or "")
    lines = s.splitlines() or ([s] if s else [])
    words = s.split()
    return ok(
        chars=len(s),
        lines=len(lines),
        words=len(words),
        empty=not bool(s.strip()),
    )
