"""OCR module — stub with optional pytesseract hook."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class OcrResult:
    ok: bool
    text: str
    note: str


class OcrModule:
    def read_image(self, path: str | Path) -> OcrResult:
        p = Path(path)
        if not p.is_file():
            return OcrResult(False, "", f"missing file: {path}")
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore

            text = pytesseract.image_to_string(Image.open(p))
            return OcrResult(True, text.strip(), "pytesseract")
        except Exception as exc:  # noqa: BLE001
            return OcrResult(
                False,
                "",
                f"OCR unavailable (optional pytesseract+Pillow): {exc}",
            )
