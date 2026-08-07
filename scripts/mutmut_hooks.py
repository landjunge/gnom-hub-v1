#!/usr/bin/env python3
"""
mutmut shell hooks (pre_mutation / post_mutation).

Configured in pyproject.toml:
  pre_mutation  = "python scripts/mutmut_hooks.py pre"
  post_mutation = "python scripts/mutmut_hooks.py post"

Lifecycle (mutmut 2.4):
  pre  → (optional) mutmut_config.pre_mutation(context)
       → shell pre_mutation          ← this script
       → mutate file + run tests
  post → restore file from .bak
       → shell post_mutation         ← this script

Jobs:
  - wipe gnom_hub __pycache__ so pytest never imports stale bytecode
  - remove orphaned *.bak if a previous run crashed mid-mutation
  - verify src-layout is present (hard fail → mutant treated as error path)
  - optional: set PYTHONPATH hint file for debugging

Exit codes: 0 ok, 2 usage, 3 hard fail (missing tree).
Stdout is captured by mutmut; keep it short when swallow_output=true.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PKG = SRC / "gnom_hub"
QUIET = os.environ.get("MUTMUT_HOOK_QUIET", "").strip() in ("1", "true", "yes")


def _log(msg: str) -> None:
    if not QUIET:
        print(f"[mutmut-hook] {msg}", flush=True)


def _clean_pycache(root: Path) -> int:
    n = 0
    if not root.is_dir():
        return 0
    for p in root.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
        n += 1
    # orphan bytecode next to sources
    for p in root.rglob("*.pyc"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    return n


def _clean_orphan_backups() -> int:
    """Remove stray mutmut backups if process died mid-run."""
    n = 0
    if not PKG.is_dir():
        return 0
    for p in PKG.rglob("*.bak"):
        # mutmut uses "<file>.bak" next to source
        try:
            p.unlink()
            n += 1
            _log(f"removed orphan backup {p.relative_to(ROOT)}")
        except OSError as exc:
            _log(f"backup cleanup failed {p}: {exc}")
    return n


def pre() -> int:
    if not SRC.is_dir() or not PKG.is_dir():
        print(f"[mutmut-hook] HARD FAIL: missing package at {PKG}", file=sys.stderr)
        return 3
    n_py = _clean_pycache(PKG)
    n_bak = _clean_orphan_backups()
    # Hint for humans / CI logs
    os.environ.setdefault("PYTHONPATH", str(SRC))
    _log(
        f"pre ok pycache_cleared={n_py} bak_removed={n_bak} PYTHONPATH={os.environ.get('PYTHONPATH')}"
    )
    return 0


def post() -> int:
    n_py = _clean_pycache(PKG)
    # After mutmut restores the file, .bak should be gone; sweep leftovers anyway
    n_bak = _clean_orphan_backups()
    _log(f"post ok pycache_cleared={n_py} bak_removed={n_bak}")
    return 0


def main(argv: list[str]) -> int:
    cmd = (argv[1] if len(argv) > 1 else "").strip().lower()
    if cmd == "pre":
        return pre()
    if cmd == "post":
        return post()
    print("usage: mutmut_hooks.py pre|post", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
