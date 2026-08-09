"""Mermaid automation — static check script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mermaid_check.py"


def _load():
    name = "gnom_mermaid_check"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mc = _load()


def test_repo_docs_pass():
    rc = mc.main([])
    assert rc == 0


def test_rejects_unknown_class(tmp_path: Path):
    md = tmp_path / "t.md"
    md.write_text(
        "```mermaid\nflowchart LR\n  A[x]:::edge\n```\n",
        encoding="utf-8",
    )
    blocks = mc.extract_blocks(md, tmp_path)
    assert len(blocks) == 1
    mc.validate_block(blocks[0])
    assert any(i.code == "unknown_shorthand" for i in blocks[0].errors)


def test_rejects_backslash_n(tmp_path: Path):
    md = tmp_path / "t.md"
    md.write_text(
        '```mermaid\nflowchart LR\n  A["x\\ny"]\n```\n',
        encoding="utf-8",
    )
    blocks = mc.extract_blocks(md, tmp_path)
    mc.validate_block(blocks[0])
    assert any(i.code == "backslash_n" for i in blocks[0].errors)


def test_palette_has_expected_core():
    assert "core" in mc.ALLOWED_CLASSES
    assert "danger" in mc.ALLOWED_CLASSES
    assert "edge" not in mc.ALLOWED_CLASSES


def test_empty_block_error():
    b = mc.Block(path="x.md", index=1, start_line=1, body="   \n")
    mc.validate_block(b)
    assert b.errors


def test_list_and_inventory(tmp_path: Path):
    inv = tmp_path / "inv.md"
    rc = mc.main(["--write-inventory", str(inv), "--list"])
    assert rc == 0
    assert inv.is_file()
    assert "Mermaid inventory" in inv.read_text(encoding="utf-8")
