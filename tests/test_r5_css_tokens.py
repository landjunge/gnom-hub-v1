"""R5.1: desk tokens live in tokens.css; app.css imports them."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = (ROOT / "src/gnom_hub/ui/static/tokens.css").read_text(encoding="utf-8")
APP = (ROOT / "src/gnom_hub/ui/static/app.css").read_text(encoding="utf-8")


def test_app_css_imports_tokens_and_has_no_second_root_palette():
    assert '@import url("tokens.css")' in APP or "@import url('tokens.css')" in APP
    assert "--btn-h: 20px" in TOKENS
    assert "--tab-h: 20px" in TOKENS
    assert "--c-flex: #f0c000" in TOKENS
    assert "--border-strong: #5c616a" in TOKENS
    assert "--btn-h: 20px" not in APP
    assert "--c-flex: #f0c000" not in APP


def test_tokens_keep_r4_sizes_and_agent_yellow():
    assert "--btn-h: 20px" in TOKENS
    assert "#a78bfa" not in TOKENS
    assert "--c-brainstorm: #ef5350" in TOKENS
