"""Read/write a local ThreadDesk packet. Never Send, never Execute, never a TD database."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from gnom_hub.memory.secrets import filter_secrets, looks_like_secret

DEFAULT_ROOT = Path.home() / ".threaddesk"
HANDOFF_NAME = "handoff.json"


def store_root() -> Path:
    raw = (os.environ.get("THREADDESK_ROOT") or "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_ROOT


def handoff_path() -> Path:
    return store_root() / HANDOFF_NAME


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def existing_handoff() -> dict[str, Any] | None:
    path = handoff_path()
    if not path.is_file():
        return None
    data = _read_json(path)
    return data or None


def build_packet(
    *,
    facts: list[str],
    run_id: str = "",
    project_id: str = "",
    purpose: str = "memory_handoff",
    overwrite_of: str | None = None,
) -> dict[str, Any]:
    clean = filter_secrets([f for f in facts if str(f).strip() and not looks_like_secret(f)])
    now = _utc_now()
    pid = (project_id or os.environ.get("GNOM_PROJECT_ID") or "personal").strip() or "personal"
    rid = (run_id or uuid.uuid4().hex[:12]).strip()
    title = clean[0][:80] if clean else "Gnom-Übergabe"
    notes = "\n".join(f"• {f}" for f in clean)
    packet = {
        "kind": "threaddesk.handoff",
        "sender": "gnom-hub-v1",
        "recipient": "threaddesk",
        "project_id": pid,
        "run_id": rid,
        "purpose": purpose,
        "data_refs": [{"kind": "warm_fact", "text": f} for f in clean],
        "valid_until": _iso(now + timedelta(days=7)),
        "approval": {
            "by": "user",
            "at": _iso(now),
            "action": "uebergeben",
        },
        "result": {"status": "handed", "facts": clean},
        "title": title,
        "notes": notes,
        "ran": False,
    }
    if overwrite_of:
        packet["replaced"] = overwrite_of
    return packet


def write_handoff(
    facts: list[str],
    *,
    run_id: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write only handoff.json. Never a database. Never execute."""
    path = handoff_path()
    if path.name != HANDOFF_NAME or path.suffix != ".json":
        return {"ok": False, "error": "refused_path", "ran": False}
    if path.suffix in {".db", ".sqlite", ".sqlite3"}:
        return {"ok": False, "error": "refused_database", "ran": False}
    prior = existing_handoff()
    if prior and not overwrite:
        return {
            "ok": False,
            "error": "conflict",
            "ran": False,
            "existing_title": str(prior.get("title") or ""),
            "path": str(path),
        }
    packet = build_packet(
        facts=facts,
        run_id=run_id,
        overwrite_of=str(prior.get("run_id") or "") if prior else None,
    )
    root = store_root()
    root.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(HANDOFF_NAME + ".tmp")
    tmp.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return {
        "ok": True,
        "ran": False,
        "path": str(path),
        "packet": packet,
        "overwrote": bool(prior),
    }


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
