#!/usr/bin/env python3
"""Scaffold a new Gnom-Hub plugin from plugins/_template."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "plugins" / "_template"


def main() -> int:
    ap = argparse.ArgumentParser(description="Create plugins/<id> from template")
    ap.add_argument("plugin_id", help="folder + plugin id (snake_case)")
    ap.add_argument("--tool", default="", help="default tool name (default: same as id)")
    ap.add_argument("--force", action="store_true", help="overwrite existing folder")
    args = ap.parse_args()
    pid = args.plugin_id.strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", pid):
        print("plugin_id must be snake_case [a-z][a-z0-9_]{1,40}", file=sys.stderr)
        return 1
    tool = (args.tool or pid).strip()
    dest = ROOT / "plugins" / pid
    if dest.exists() and not args.force:
        print(f"exists: {dest} (use --force)", file=sys.stderr)
        return 1
    if not TEMPLATE.is_dir():
        print(f"missing template: {TEMPLATE}", file=sys.stderr)
        return 1
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(TEMPLATE, dest)
    # rewrite manifest
    mj = dest / "plugin.json"
    meta = json.loads(mj.read_text(encoding="utf-8"))
    meta["id"] = pid
    meta["name"] = pid.replace("_", " ").title()
    if meta.get("tools"):
        meta["tools"][0]["name"] = tool
        meta["tools"][0]["description"] = f"{tool} (scaffolded)"
    mj.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    main_py = dest / "main.py"
    text = main_py.read_text(encoding="utf-8")
    text = text.replace('plugin="my_plugin"', f'plugin="{pid}"')
    text = text.replace("my_plugin", pid)
    main_py.write_text(text, encoding="utf-8")
    print(f"Created {dest}")
    print("  edit plugin.json + main.py, restart hub or POST /api/plugins/reload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
