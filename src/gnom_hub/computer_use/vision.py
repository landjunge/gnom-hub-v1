"""Vision + teaching notes (lite: describe file existence + size)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class VisionResult:
    ok: bool
    description: str
    teaching: str


class VisionModule:
    def describe(self, path: str | Path) -> VisionResult:
        p = Path(path)
        if not p.is_file():
            return VisionResult(False, "no image", "Provide a valid image path.")
        size = p.stat().st_size
        return VisionResult(
            True,
            f"Image {p.name} ({size} bytes)",
            "Teaching: mark UI targets with labels in a later vision model step.",
        )
