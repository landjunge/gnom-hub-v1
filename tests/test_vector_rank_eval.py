"""Regression: vector rank-eval gold set must stay above thresholds."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vector_rank_eval_script_passes():
    script = ROOT / "scripts" / "vector_rank_eval.py"
    assert script.is_file()
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout
    assert "phrase_trap" in proc.stdout or "phrase_trap P@1" in proc.stdout


def test_vector_rank_eval_json_metrics():
    script = ROOT / "scripts" / "vector_rank_eval.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["pass"] is True
    assert report["p_at_1"] >= 0.85
    assert report["mrr"] >= 0.90
    assert report["source_ok_at_1"] >= 0.75
    assert report["avg_margin"] >= 0.05
    assert report["n"] >= 8
    assert report["phrase_trap_n"] >= 3
    assert "phrase_trap_p_at_1" in report
