"""mutmut shell hooks — pycache cleanup and hard-fail paths."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "mutmut_hooks.py"


def test_hook_pre_post_exit_zero():
    env = {**dict(**__import__("os").environ), "MUTMUT_HOOK_QUIET": "1", "PYTHONPATH": "src"}
    for cmd in ("pre", "post"):
        r = subprocess.run(
            [sys.executable, str(HOOK), cmd],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert r.returncode == 0, r.stderr + r.stdout


def test_hook_usage_error():
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 2


def test_hook_pre_clears_pycache(tmp_path, monkeypatch):
    # Create a fake pycache under real package and ensure pre removes it
    pkg = ROOT / "src" / "gnom_hub" / "agents"
    cache = pkg / "__pycache__"
    cache.mkdir(exist_ok=True)
    marker = cache / "mutmut_hook_test.pyc"
    marker.write_bytes(b"\0")
    r = subprocess.run(
        [sys.executable, str(HOOK), "pre"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**dict(**__import__("os").environ), "MUTMUT_HOOK_QUIET": "1"},
    )
    assert r.returncode == 0
    assert not marker.exists()


def test_mutmut_config_importable():
    # Must be importable from project root (mutmut does this)
    sys.path.insert(0, str(ROOT))
    import mutmut_config

    class Ctx:
        current_source_line = "# just a comment"
        skip = False

    ctx = Ctx()
    mutmut_config.pre_mutation(ctx)
    assert ctx.skip is True

    ctx2 = Ctx()
    ctx2.current_source_line = "return not _is_clear_build(t)"
    ctx2.skip = False
    mutmut_config.pre_mutation(ctx2)
    assert ctx2.skip is False
