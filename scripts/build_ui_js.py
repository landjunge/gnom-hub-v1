#!/usr/bin/env python3
"""Concatenate ui/static/parts/*.js → ui/static/app.js (order by filename)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "src" / "gnom_hub" / "ui" / "static" / "parts"
OUT = ROOT / "src" / "gnom_hub" / "ui" / "static" / "app.js"


def main() -> None:
    files = sorted(PARTS.glob("*.js"))
    if not files:
        raise SystemExit(f"no parts in {PARTS}")
    body = "".join(p.read_text(encoding="utf-8") for p in files)
    # Strip part banners so runtime app.js stays clean? Keep them — harmless in JS block comments.
    OUT.write_text(body, encoding="utf-8")
    print(f"built {OUT.relative_to(ROOT)} from {len(files)} parts ({len(body)} bytes)")


if __name__ == "__main__":
    main()
