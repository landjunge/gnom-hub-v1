"""Computer-Use kit: Capture → Vision → OCR → Action."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gnom_hub.computer_use.action import ActionModule
from gnom_hub.computer_use.capture import CaptureModule
from gnom_hub.computer_use.ocr import OcrModule
from gnom_hub.computer_use.vision import VisionModule
from gnom_hub.config.paths import project_root


class ComputerUseKit:
    def __init__(self, root: Path | None = None, *, god_mode: bool = False) -> None:
        self.root = Path(root) if root is not None else project_root()
        out = self.root / "data" / "computer_use"
        self.capture = CaptureModule(out)
        self.vision = VisionModule()
        self.ocr = OcrModule()
        self.action = ActionModule(god_mode_enabled=god_mode)

    def set_god_mode(self, enabled: bool) -> None:
        self.action.set_god_mode(enabled)

    def inspect_screen(self) -> dict[str, Any]:
        cap = self.capture.screenshot("last.png")
        vis = self.vision.describe(cap.path or "")
        ocr = self.ocr.read_image(cap.path or "") if cap.path else None
        return {
            "capture": {"ok": cap.ok, "path": cap.path, "note": cap.note},
            "vision": {"ok": vis.ok, "description": vis.description, "teaching": vis.teaching},
            "ocr": {
                "ok": bool(ocr and ocr.ok),
                "text": (ocr.text if ocr else ""),
                "note": (ocr.note if ocr else "skipped"),
            },
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "modules": ["capture", "vision", "ocr", "action", "workflow"],
            "action": self.action.snapshot(),
            "out_dir": str(self.root / "data" / "computer_use"),
        }
