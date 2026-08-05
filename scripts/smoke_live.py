#!/usr/bin/env python3
"""
Optional live DeepSeek smoke. Skips cleanly when DEEPSEEK_API_KEY is missing.

Usage:
  PYTHONPATH=src python scripts/smoke_live.py
  GNOM_LIVE_SMOKE=1  — fail if key missing (CI optional job)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gnom_hub.config.keys import ensure_env_from_key_txt, has_deepseek_key, load_keys
from gnom_hub.llm import LLMManager, LLMMessage


def main() -> int:
    require = os.getenv("GNOM_LIVE_SMOKE", "").strip().lower() in ("1", "true", "yes")
    ensure_env_from_key_txt(ROOT)
    keys = load_keys(ROOT)
    if not has_deepseek_key(keys):
        msg = "SKIP live smoke: no DEEPSEEK_API_KEY"
        print(msg)
        return 1 if require else 0

    # Ensure thinking-off path is used (empty content was a v4-flash default issue)
    os.environ.setdefault("DEEPSEEK_THINKING", "0")
    llm = LLMManager(keys=keys)
    result = llm.chat(
        [
            LLMMessage(role="system", content="Reply with exactly one word: pong"),
            LLMMessage(role="user", content="ping"),
        ],
        max_tokens=32,
        agent="smoke_live",
    )
    content = (result.content or "").strip()
    print(f"  model={result.model}")
    print(f"  content={content[:80]!r}")
    print(f"  tokens={result.prompt_tokens}+{result.completion_tokens}")
    print(f"  cost_usd={result.cost_usd:.8f}")
    if not content:
        print("LIVE_SMOKE FAIL: empty content", file=sys.stderr)
        return 2
    print("LIVE_SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
