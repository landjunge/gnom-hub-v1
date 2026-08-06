#!/usr/bin/env python3
"""
Canonical landing-page E2E — thin wrapper around user_scenarios_e2e S1.

Prefer the full suite:
  python scripts/user_scenarios_e2e.py           # S1 + S5 (UI + Tools)
  python scripts/user_scenarios_e2e.py --all     # S1–S5
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = os.environ.copy()
    cmd = [sys.executable, str(ROOT / "scripts" / "user_scenarios_e2e.py"), "--only", "1"]
    print("user_landing_e2e → user_scenarios_e2e --only 1")
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
