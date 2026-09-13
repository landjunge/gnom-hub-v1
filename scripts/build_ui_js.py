#!/usr/bin/env python3
"""Concatenate ui/static/parts/*.js → ui/static/app.js (order by filename).

Edit parts/*.js, then run this script. Do not edit app.js by hand.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "src" / "gnom_hub" / "ui" / "static" / "parts"
OUT = ROOT / "src" / "gnom_hub" / "ui" / "static" / "app.js"


def built_text() -> str:
    files = sorted(PARTS.glob("*.js"))
    if not files:
        raise SystemExit(f"no parts in {PARTS}")
    return "".join(p.read_text(encoding="utf-8") for p in files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if app.js does not match a fresh build",
    )
    args = parser.parse_args()
    text = built_text()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("app.js is stale — run: python3 scripts/build_ui_js.py", file=sys.stderr)
            return 1
        print(f"ok {OUT.relative_to(ROOT)} matches {len(sorted(PARTS.glob('*.js')))} parts")
        return 0
    OUT.write_text(text, encoding="utf-8")
    files = sorted(PARTS.glob("*.js"))
    print(f"built {OUT.relative_to(ROOT)} from {len(files)} parts ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
