#!/usr/bin/env python3
"""pre/post hooks for mutmut — keep import path and bytecode clean."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pre() -> None:
    # Ensure src layout is importable for the runner process tree
    src = ROOT / "src"
    print(f"[mutmut-hook pre] ROOT={ROOT} src={src.is_dir()}", flush=True)
    # Drop stale pyc under mutated package to avoid loading old bytecode
    pkg = src / "gnom_hub"
    if pkg.is_dir():
        for p in pkg.rglob("__pycache__"):
            shutil.rmtree(p, ignore_errors=True)


def post() -> None:
    # mutmut restores the file; just clear pyc again
    pkg = ROOT / "src" / "gnom_hub"
    if pkg.is_dir():
        for p in pkg.rglob("__pycache__"):
            shutil.rmtree(p, ignore_errors=True)
    print("[mutmut-hook post] cleaned __pycache__", flush=True)


def main(argv: list[str]) -> int:
    cmd = (argv[1] if len(argv) > 1 else "").strip().lower()
    if cmd == "pre":
        pre()
        return 0
    if cmd == "post":
        post()
        return 0
    print("usage: mutmut_hooks.py pre|post", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
