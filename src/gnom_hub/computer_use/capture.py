"""Screen capture — real if optional deps exist, else stub."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CaptureResult:
    ok: bool
    path: str | None
    note: str


class CaptureModule:
    def __init__(self, out_dir: Path) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def screenshot(self, name: str = "screen.png") -> CaptureResult:
        safe = Path(name).name
        path = self.out_dir / safe
        # Try Pillow ImageGrab (often available); never hard-require
        try:
            from PIL import ImageGrab  # type: ignore

            img = ImageGrab.grab()
            img.save(path)
            return CaptureResult(True, str(path), "captured via Pillow ImageGrab")
        except Exception as exc:  # noqa: BLE001
            # Write a tiny placeholder so path exists for workflow demos
            path.write_bytes(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
                b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
                b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            return CaptureResult(
                False,
                str(path),
                f"stub capture (install Pillow for real screenshots): {exc}",
            )
