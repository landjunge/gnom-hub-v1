"""Mutation check for pure helpers — fails if a mutant survives assertions."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mutation_check_kills_helpers_mutants():
    script = ROOT / "scripts" / "mutation_check.py"
    assert script.is_file()
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-1000:]
