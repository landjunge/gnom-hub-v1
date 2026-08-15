"""Read a local ThreadDesk packet. Never Send, never Execute."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path.home() / ".threaddesk"


def store_root() -> Path:
    raw = (os.environ.get("THREADDESK_ROOT") or "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_ROOT


def peek() -> dict[str, Any]:
    root = store_root()
    chat_path = root / "gnom-chat.json"
    meta_path = root / "gnom.json"
    handoff_path = root / "handoff.json"
    text = ""
    kind = ""
    mode = ""
    title = ""
    path = ""
    if chat_path.is_file():
        data = _read_json(chat_path)
        text = str(data.get("text") or "").strip()
        kind = "threaddesk.gnom"
        path = str(chat_path)
    if meta_path.is_file():
        meta = _read_json(meta_path)
        kind = str(meta.get("kind") or kind or "threaddesk.gnom")
        mode = str(meta.get("mode") or "")
        title = str(meta.get("title") or "")
        if not text:
            text = str(meta.get("prompt") or "").strip()
        if not path:
            path = str(meta_path)
    if not text and handoff_path.is_file():
        ho = _read_json(handoff_path)
        title = str(ho.get("title") or title)
        notes = str(ho.get("notes") or "").strip()
        desc = str(ho.get("description") or "").strip()
        text = "\n\n".join(p for p in (title, desc, notes) if p)
        kind = str(ho.get("kind") or "threaddesk.handoff")
        path = str(handoff_path)
    preview = " ".join(text.split())
    if len(preview) > 80:
        preview = preview[:79] + "…"
    return {
        "ok": True,
        "present": bool(text),
        "kind": kind,
        "mode": mode,
        "title": title,
        "text": text,
        "preview": preview,
        "path": path,
        "ran": False,
        "instruction": "Fill the chat box only. Do not Send or Execute unless the user presses it.",
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}
